extends CharacterBody2D

# Initial delay before damage begins
const BURN_DELAY : float = 2.0
# Delay between damage triggers
const BURN_RATE  : float = 1.0
# Initial delay before healing begins
const HEAL_DELAY : float = 4.0
# Delay between damage triggers
const HEAL_RATE  : float = 1.0

@export var speed         : float = 50.0
@export var jump_velocity : float = -500.0
@export var stop_radius   : float = 8.0
@export var stop_smooth_time = 0.18
var stop_tween: Tween
var player_inside   : bool    = false
var player          : Node    = null
var mouse_direction : Vector2 = Vector2.ZERO
var sun_timer       : float   = 0.0
var sun_damage      : int     = 1
var moon_timer      : float   = 0.0
var moon_heal       : int     = 1
var burning         : bool    = false
var current_damage  : int     = 0
var healing         : bool    = false
var current_heal    : int     = 0

func _ready():
	# If you want, assign via group instead (recommended)
	player = get_tree().get_first_node_in_group("player")

	$Area2D.body_entered.connect(_on_body_entered)
	$Area2D.body_exited.connect(_on_body_exited)


func _physics_process(delta):
	var to_mouse = get_global_mouse_position() - global_position
	var distance_to_mouse = to_mouse.length()

	if distance_to_mouse > stop_radius:
		if is_instance_valid(stop_tween):
			stop_tween.kill()
			stop_tween = null
		mouse_direction = to_mouse.normalized()
		velocity = mouse_direction * speed
	else:
		mouse_direction = Vector2.ZERO
		if not is_instance_valid(stop_tween) and velocity.length() > 0.0:
			stop_tween = create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
			stop_tween.tween_property(self, "velocity", Vector2.ZERO, stop_smooth_time)
			stop_tween.finished.connect(func(): stop_tween = null)
		elif not is_instance_valid(stop_tween):
			velocity = Vector2.ZERO
	if player:
		update_health(delta)
	move_and_slide()

func _on_body_entered(body):
	if body == player:
		player_inside = true
		print("Entered shadow")

func _on_body_exited(body):
	if body == player:
		player_inside = false
		print("Exited shadow")

#func _on_area_2d_body_entered(body: Node2D) -> void:
	#print("Entered shadow")
	#pass # Replace with function body.
#
#
#func _on_area_2d_body_exited(body: Node2D) -> void:
	#print("Exited shadow")
	#pass # Replace with function body.

	# DAMAGE LOGIC: only if player is NOT under shadow
func update_health(delta : float) -> void:
	if burning and !SFX.is_playing("vamp_burning"):
		SFX.create_sound("vamp_burning")
	elif !burning and SFX.is_playing("vamp_burning"):
		SFX.destroy_sounds("vamp_burning")
	if healing and !SFX.is_playing("vamp_healing"):
		SFX.create_sound("vamp_healing")
	elif !healing and SFX.is_playing("vamp_healing"):
		SFX.destroy_sounds("vamp_healing")
	if !player_inside:
		moon_timer = 0.0
		current_heal = 0
		healing = false
		sun_timer += delta
		if sun_timer == delta:
			SFX.destroy_sounds("vamp_warning")
			SFX.create_sound("vamp_warning")
		elif sun_timer >= (current_damage * BURN_RATE) + BURN_DELAY:
			if player.health <= 0: return
			player.take_damage(sun_damage)
			current_damage += sun_damage
			if player.health <= 0:
				player.health = 0
				burning = false
				SFX.destroy_sounds("vamp_dead")
				SFX.create_sound("vamp_dead", -4.0)
				print("Vampy has 0 health")
			else: 
				burning = true
				SFX.destroy_sounds("vamp_sizzle")
				SFX.create_sound("vamp_sizzle")
				print("Taking damage")
	else:
		sun_timer = 0.0
		current_damage = 0
		burning = false
		moon_timer += delta
		if moon_timer == delta:
			SFX.destroy_sounds("vamp_phew")
			SFX.create_sound("vamp_phew", -4.0)
		elif moon_timer >= (current_heal * HEAL_RATE) + HEAL_DELAY:
			if player.health >= player.max_health: return
			player.heal_damage(moon_heal)
			current_heal += moon_heal
			if player.health >= player.max_health:
				player.health = player.max_health
				healing = false
				SFX.destroy_sounds("vamp_max_health")
				SFX.create_sound("vamp_max_health")
				print("Vampy has max health")
			else:
				healing = true
				SFX.destroy_sounds("vamp_heal")
				SFX.create_sound("vamp_heal")
				print("Healing damage")
