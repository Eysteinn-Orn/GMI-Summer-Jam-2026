extends Camera3D

@export var target: NodePath

var follow_offset: Vector3

func _ready() -> void:
	var t := get_node_or_null(target)
	if t:
		follow_offset = global_position - t.global_position

func _process(_delta: float) -> void:
	var t := get_node_or_null(target)
	if t:
		global_position = t.global_position + follow_offset
