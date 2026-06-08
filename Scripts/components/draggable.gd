class_name Draggable
extends Node

@export var can_drag := true
@export var drag_priority := 0
var dragged_by: Node = null

func begin_drag(by: Node) -> bool:
    if not can_drag or dragged_by != null:
        return false
    dragged_by = by
    return true

func end_drag() -> void:
    dragged_by = null

func drag_to(_target: Vector2, _delta: float) -> void:
    # implement in subclass
    pass