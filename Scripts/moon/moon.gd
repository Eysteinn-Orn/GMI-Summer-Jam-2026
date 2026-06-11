extends CharacterBody2D

# Initial delay before damage begins
const BURN_DELAY : float = 2.0
# Delay between damage triggers
const BURN_RATE  : float = 1.0
# Initial delay before healing begins
const HEAL_DELAY : float = 4.0
# Delay between damage triggers
const HEAL_RATE  : float = 1.0
const STOP_SMOOTH_TIME = 0.18
const DISSIPATE_DURATION : float = 1.0

@onready var shadow_shape: CollisionShape2D = $Area2D/CollisionShape2D
@onready var darkness: Node2D = $Darkness
@export var speed         : float = 50.0
@export var jump_velocity : float = -500.0
@export var stop_radius   : float = 20.0
@export var stop_smooth_time      = STOP_SMOOTH_TIME
@export var dissipate_duration: float = DISSIPATE_DURATION
@export var player        : Node  = null
@export var ui : CanvasLayer
var stop_tween: Tween
var shadow_dissipate_tween: Tween
var player_inside   : bool    = false
var mouse_direction : Vector2 = Vector2.ZERO
var sun_timer       : float   = 0.0
var sun_damage      : int     = 1
var moon_timer      : float   = 0.0
var moon_heal       : int     = 1
var burning         : bool    = false
var current_damage  : int     = 0
var healing         : bool    = false
var current_heal    : int     = 0
var lvl_progress    : float   = 0
var _shadow_dissipated: bool  = false

func _physics_process(delta):
	var to_mouse = get_global_mouse_position() - global_position
	var distance_to_mouse = to_mouse.length()
	var shadow_radius := 0.0
	if shadow_shape and shadow_shape.shape:
		shadow_radius = shadow_shape.shape.radius
	darkness.core_radius = shadow_radius
	stop_radius = shadow_radius / 5
	stop_smooth_time = STOP_SMOOTH_TIME * (shadow_radius / 60)
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

func is_shadow_dissipated() -> bool:
	return _shadow_dissipated

func dissipate_shadow() -> void:
	if _shadow_dissipated:
		return
	_shadow_dissipated = true
	player_inside = false
	healing = false
	moon_timer = 0.0
	current_heal = 0

	if is_instance_valid(shadow_dissipate_tween):
		shadow_dissipate_tween.kill()

	if not shadow_shape or not shadow_shape.shape:
		darkness.core_radius = 0.0
		return

	var duration := maxf(0.01, dissipate_duration)
	shadow_dissipate_tween = create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	shadow_dissipate_tween.tween_property(shadow_shape.shape, "radius", 0.0, duration)
	shadow_dissipate_tween.parallel().tween_property(darkness, "core_radius", 0.0, duration)
	shadow_dissipate_tween.finished.connect(func(): shadow_dissipate_tween = null)

func _on_body_entered(body):
	if body == player:
		player_inside = true
		print("Entered shadow")

func _on_body_exited(body):
	if body == player:
		player_inside = false
		print("Exited shadow")

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
			lvl_progress = ui.lvl_progress
			SFX.destroy_sounds("vamp_warning")
			SFX.create_sound("vamp_warning")
		elif sun_timer >= (
			(current_damage * BURN_RATE) +
			(BURN_DELAY * (1 - lvl_progress))
			):
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
		moon_timer += delta
		if moon_timer == delta:
			lvl_progress = ui.lvl_progress
			if burning:
				SFX.destroy_sounds("vamp_phew")
				SFX.create_sound("vamp_phew", -4.0)
		sun_timer = 0.0
		current_damage = 0
		burning = false
		if moon_timer == delta: pass
		elif moon_timer >= (
			(current_heal * HEAL_RATE) + 
			(HEAL_DELAY * (lvl_progress))
			):
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
