extends Sprite3D

@export var viewport_path: NodePath

func _ready() -> void:
	var vp := get_node(viewport_path) as SubViewport
	var bounds := Rect2()
	for child in vp.get_children():
		bounds = _collect_tilemap_bounds(child, bounds)
	if bounds.size.x > 0 and bounds.size.y > 0:
		bounds = bounds.grow(32)
		vp.size = Vector2i(bounds.size)
		vp.canvas_transform = Transform2D(0, -bounds.position)
	texture = vp.get_texture()

func _collect_tilemap_bounds(node: Node, bounds: Rect2) -> Rect2:
	if node is TileMapLayer:
		var used: Rect2i = node.get_used_rect()
		var tile_size := Vector2i(16, 16)
		if node.tile_set:
			tile_size = node.tile_set.tile_size
		var pixel_rect := Rect2(Vector2(used.position) * Vector2(tile_size), Vector2(used.size) * Vector2(tile_size))
		if bounds.size == Vector2.ZERO:
			bounds = pixel_rect
		else:
			bounds = bounds.merge(pixel_rect)
	for child in node.get_children():
		bounds = _collect_tilemap_bounds(child, bounds)
	return bounds
