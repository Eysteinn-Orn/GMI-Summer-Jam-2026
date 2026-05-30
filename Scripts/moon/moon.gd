extends CharacterBody2D

@export var speed = 50.0
@export var jump_velocity = -500.0
@export var damage_per_second = 10.0

var player_inside := false
var player: Node = null


func _ready():
	# If you want, assign via group instead (recommended)
	player = get_tree().get_first_node_in_group("player")

	$Area2D.body_entered.connect(_on_body_entered)
	$Area2D.body_exited.connect(_on_body_exited)
	


func _physics_process(delta):
	var direction = Vector2(
		Input.get_axis("Left2", "Right2"),
		Input.get_axis("Up2", "Down2")
	)

	velocity = direction.normalized() * speed
	move_and_slide()

	# DAMAGE LOGIC: only if player is NOT under shadow
	if player and not player_inside:
		if player.has_method("take_damage"):
			player.take_damage(damage_per_second * delta)


func _on_body_entered(body):
	if body == player:
		player_inside = true
		print("Entered shadow")


func _on_body_exited(body):
	if body == player:
		player_inside = false
		print("Exited shadow")

func _on_area_2d_body_entered(body: Node2D) -> void:
	print("Entered shadow")
	pass # Replace with function body.


func _on_area_2d_body_exited(body: Node2D) -> void:
	print("Exited shadow")
	pass # Replace with function body.
