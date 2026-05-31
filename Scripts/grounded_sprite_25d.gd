extends Sprite3D

func _ready() -> void:
	add_to_group("grounded_sprites")
	var cam := get_viewport().get_camera_3d()
	if cam:
		rotation.x = cam.rotation.x
	update_grounding()

func update_grounding() -> void:
	if texture:
		var h := texture.get_height() * pixel_size * scale.y
		position.y = h / 2.0 * abs(cos(rotation.x))
