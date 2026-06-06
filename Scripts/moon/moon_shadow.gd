extends Node2D
## Radial darkening cast by the moon: a solid dark core whose radius matches the
## moon sprite, fading to nothing a bit beyond it. Drawn procedurally (no
## texture) on a high z_index so it darkens the player and any other sprite that
## falls inside the circle. Lives as a child of Moon, so it follows it around.

@export var darkness  : float = 0.6   # alpha of the black core (0..1)
@export_range(0.0, 1.0) var hold : float = 0.0  # fraction of the falloff held at full dark
@export var falloff   : float = 90.0  # local px the fade extends past the core
@export var segments  : int   = 64    # circle smoothness
@export var sprite_path : NodePath    # the moon Sprite2D to size the core from

var core_radius : float = 64.0

func _ready() -> void:
	var spr := get_node_or_null(sprite_path) as Sprite2D
	if spr and spr.texture:
		var size := spr.texture.get_size() * spr.scale
		core_radius = max(size.x, size.y) * 0.5
	queue_redraw()

func _draw() -> void:
	var solid := Color(0.0, 0.0, 0.0, darkness)
	var clear := Color(0.0, 0.0, 0.0, 0.0)
	var hold_r := core_radius + falloff * hold  # stays full dark out to here
	var outer := core_radius + falloff
	var step := TAU / segments
	for i in segments:
		var d0 := Vector2(cos(i * step), sin(i * step))
		var d1 := Vector2(cos((i + 1) * step), sin((i + 1) * step))
		# Uniform dark disc out to hold_r, then a band fading to transparent.
		draw_colored_polygon(
			PackedVector2Array([Vector2.ZERO, d0 * hold_r, d1 * hold_r]), solid)
		draw_polygon(
			PackedVector2Array([d0 * hold_r, d1 * hold_r, d1 * outer, d0 * outer]),
			PackedColorArray([solid, solid, clear, clear]))
