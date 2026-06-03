extends CharacterBody2D

@export var speed = 50.0
@export var jump_velocity = -500.0
@export var stop_radius = 8.0

var player_inside := false
var player: Node = null
var mouse_direction: Vector2 = Vector2.ZERO
var sun_timer := 0.0


func _ready():
	# If you want, assign via group instead (recommended)
	player = get_tree().get_first_node_in_group("player")

	$Area2D.body_entered.connect(_on_body_entered)
	$Area2D.body_exited.connect(_on_body_exited)


func _physics_process(delta):
	var to_mouse = get_global_mouse_position() - global_position
	var distance_to_mouse = to_mouse.length()

	if distance_to_mouse > stop_radius:
		mouse_direction = to_mouse.normalized()
		velocity = mouse_direction * speed
	else:
		mouse_direction = Vector2.ZERO
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
