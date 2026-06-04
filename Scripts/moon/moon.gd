extends CharacterBody2D

@export var speed = 50.0
@export var jump_velocity = -500.0
@export var stop_radius = 8.0
@export var stop_smooth_time = 0.18

var player_inside := false
var player: Node = null
var mouse_direction: Vector2 = Vector2.ZERO
var sun_timer := 0.0
var moon_timer := 0.0
var stop_tween: Tween


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

	move_and_slide()

	# DAMAGE LOGIC: only if player is NOT under shadow
	if player and not player_inside:
		sun_timer += delta

		if sun_timer >= 3.0:
			player.take_damage(1)
			sun_timer = 0.0
			print("Taking damage")
	else:
		sun_timer = 0.0
		
	if player and player_inside:
		moon_timer += delta
		
		if moon_timer >= 5.0:
			player.heal_damage(1)
			moon_timer = 0.0
			print("Healing")
	
	else: 
		moon_timer = 0.0
			


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
