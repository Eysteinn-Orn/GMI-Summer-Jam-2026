extends CharacterBody2D

var _hop_time := 0.0
var prev_prev_hop := 0.1
var prev_hop := 0.0


@onready var animation_tree: AnimationTree = %AnimationTree
@export var speed = 200.0
@export var jump_velocity = -500.0
@export var hop_height := 8.0
@export var hop_speed := 12.0
@export var max_health = 10
@export var health = 10

@onready var sprite: Sprite2D = $Sprite2D
@export var ui : CanvasLayer

func _physics_process(delta):
	var direction = Vector2(
		Input.get_axis("Left", "Right"),
		Input.get_axis("Up", "Down")
	)

	velocity = direction.normalized() * speed
	# move_and_slide()
	move_and_collide(velocity * delta)
	# update_frame(direction)
	if velocity == Vector2.ZERO:
		pass
	else:
		animation_tree.set("parameters/walk/blend_position", velocity)

	if direction.length() > 0.01:
		_hop_time += delta * hop_speed
		sprite.position.y = -abs(sin(_hop_time)) * hop_height
		if has_hopped():
			ui.update_vamp(true)
			SFX.destroy_sounds("step")
			SFX.create_sound("step", -8.0)
		prev_prev_hop = prev_hop
		prev_hop = sprite.position.y
	else:
		ui.update_vamp(false)
		_hop_time = 0.0
		sprite.position.y = 0.0
		prev_prev_hop = 0.1
		prev_hop = 0.0

func has_hopped() -> bool:
	if prev_hop >= prev_prev_hop: return false
	if sprite.position.y < prev_hop: return false
	return true

func take_damage(amount):
	health -= amount
	health = clamp(health, 0, max_health)
	ui.update_health_bar(health)
	
func heal_damage(amount):
	health += amount
	health = clamp(health, 0, max_health)
	ui.update_health_bar(health)

func update_frame(direction: Vector2):
	if direction.y > 0:
		sprite.frame_coords.y = 0
		if direction.x < 0: sprite.frame_coords.x = 0
		elif direction.x > 0: sprite.frame_coords.x = 2
		else: sprite.frame_coords.x = 1
	elif direction.y < 0:
		sprite.frame_coords.y = 3
		if direction.x < 0: sprite.frame_coords.x = 0
		elif direction.x > 0: sprite.frame_coords.x = 2
		else: sprite.frame_coords.x = 1
	elif direction.x > 0:
		sprite.frame_coords.y = 2
		sprite.frame_coords.x = 1
	elif direction.x < 0:
		sprite.frame_coords.y = 1
		sprite.frame_coords.x = 1
	else:
		sprite.frame_coords.y = 0
		sprite.frame_coords.x = 1
