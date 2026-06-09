extends CharacterBody2D

@export var speed := 50.0
@export var hop_height := 8.0
@export var hop_speed := 12.0
@export var travel_distance := 80.0
@export var bubble_interval := 4.0
@export var bubble_duration := 2.0

@onready var animation_tree: AnimationTree = %AnimationTree
@onready var sprite: Sprite2D = $Sprite2D
@onready var bubble: Label = $Bubble

var _origin_x := 0.0
var _dir := 1.0
var _hop_time := 0.0
var _bubble_t := 0.0
var _bubble_visible := false

func _ready() -> void:
	_origin_x = position.x
	bubble.visible = false

func _physics_process(delta: float) -> void:
	if absf(position.x - _origin_x) >= travel_distance:
		_dir = -_dir
		position.x = _origin_x + signf(position.x - _origin_x) * travel_distance

	var direction := Vector2(_dir, 0.0)
	velocity = direction * speed
	var collision := move_and_collide(velocity * delta)
	if collision != null:
		_dir = -_dir

	animation_tree.set("parameters/walk/blend_position", direction)

	_hop_time += delta * hop_speed
	sprite.position.y = -absf(sin(_hop_time)) * hop_height

	_bubble_t += delta
	if _bubble_visible and _bubble_t >= bubble_duration:
		bubble.visible = false
		_bubble_visible = false
		_bubble_t = 0.0
	elif not _bubble_visible and _bubble_t >= bubble_interval:
		bubble.visible = true
		_bubble_visible = true
		_bubble_t = 0.0
