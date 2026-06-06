@tool
extends EditorPlugin

## Drop any PNG into res://Assets/sprites/tiles/ and it becomes a cell in a
## single packed atlas source inside the project TileSet. One source, one
## panel — pick a tile and paint, no two-click ceremony.
##
## Stability: each PNG is assigned an atlas index the first time it's seen and
## that index is persisted in MANIFEST_PATH. Indices are never reused, even
## when a file is deleted, so already-painted tiles keep pointing at the same
## image. Re-adding a file under the same path restores its original cell.
##
## Each tile gets a full-cell collision polygon on every physics layer the
## tileset defines, so painting on a collidable TileMapLayer (e.g. Walls)
## just works.

const TILES_DIR := "res://Assets/sprites/tiles"
const TILESET_PATH := "res://Assets/tilesets/graveyard.tres"
const ATLAS_PATH := "res://Assets/tilesets/custom_tiles.png"
const MANIFEST_PATH := "res://Assets/tilesets/custom_tiles_manifest.json"
const LEGACY_META_KEY := "custom_tiles_path"
const SOURCE_ID := 1000
const COLS := 16
const MENU_ITEM := "Sync Custom Tiles"

var _syncing := false

func _enter_tree() -> void:
	add_tool_menu_item(MENU_ITEM, _sync)
	var fs := EditorInterface.get_resource_filesystem()
	fs.filesystem_changed.connect(_on_fs_changed)
	fs.resources_reimported.connect(_on_resources_reimported)
	call_deferred("_sync")

func _exit_tree() -> void:
	remove_tool_menu_item(MENU_ITEM)
	var fs := EditorInterface.get_resource_filesystem()
	if fs.filesystem_changed.is_connected(_on_fs_changed):
		fs.filesystem_changed.disconnect(_on_fs_changed)
	if fs.resources_reimported.is_connected(_on_resources_reimported):
		fs.resources_reimported.disconnect(_on_resources_reimported)

func _on_fs_changed() -> void:
	if not _syncing:
		_sync()

func _on_resources_reimported(paths: PackedStringArray) -> void:
	if _syncing:
		return
	for p in paths:
		if p.begins_with(TILES_DIR + "/"):
			_sync()
			return

func _sync() -> void:
	if _syncing:
		return
	_syncing = true
	_do_sync()
	_syncing = false

func _do_sync() -> void:
	var tileset := ResourceLoader.load(TILESET_PATH) as TileSet
	if tileset == null:
		push_error("Custom Tiles: could not load %s" % TILESET_PATH)
		return
	var tile_size := tileset.tile_size
	var paths := _list_pngs(TILES_DIR)

	var manifest := _load_manifest()
	var assignments: Dictionary = manifest.get("tiles", {})
	var next_index: int = int(manifest.get("next_index", 0))

	var changed := _purge_legacy_sources(tileset)

	# Validate every PNG and assign a stable index to any new ones.
	var present: Dictionary = {}  # int index -> Image
	for path in paths:
		var img := Image.load_from_file(ProjectSettings.globalize_path(path))
		if img == null:
			push_error("Custom Tiles: failed to load %s" % path)
			continue
		if img.get_width() != tile_size.x or img.get_height() != tile_size.y:
			push_error("Custom Tiles: %s is %dx%d; expected %dx%d" % [
				path, img.get_width(), img.get_height(), tile_size.x, tile_size.y,
			])
			continue
		if img.get_format() != Image.FORMAT_RGBA8:
			img.convert(Image.FORMAT_RGBA8)
		if not assignments.has(path):
			assignments[path] = next_index
			next_index += 1
		present[int(assignments[path])] = img

	# Persist the manifest now so an interrupted sync can't lose an index.
	manifest["tiles"] = assignments
	manifest["next_index"] = next_index
	_save_manifest(manifest)

	if assignments.is_empty():
		if tileset.has_source(SOURCE_ID):
			tileset.remove_source(SOURCE_ID)
			ResourceSaver.save(tileset, TILESET_PATH)
		return

	# Atlas grid spans every index ever assigned, so coords don't shift when
	# new tiles are added or old ones removed.
	var max_index := -1
	for v in assignments.values():
		max_index = max(max_index, int(v))
	var rows := max_index / COLS + 1
	var atlas_img := Image.create(COLS * tile_size.x, rows * tile_size.y, false, Image.FORMAT_RGBA8)
	for idx in present.keys():
		var coord := _coord_for(int(idx))
		atlas_img.blit_rect(
			present[idx],
			Rect2i(0, 0, tile_size.x, tile_size.y),
			Vector2i(coord.x * tile_size.x, coord.y * tile_size.y),
		)

	var abs_atlas := ProjectSettings.globalize_path(ATLAS_PATH)
	var fs := EditorInterface.get_resource_filesystem()
	var atlas_rewritten := false
	if not _png_matches(abs_atlas, atlas_img):
		atlas_img.save_png(abs_atlas)
		fs.update_file(ATLAS_PATH)
		fs.reimport_files(PackedStringArray([ATLAS_PATH]))
		atlas_rewritten = true

	var tex := ResourceLoader.load(ATLAS_PATH, "Texture2D", ResourceLoader.CACHE_MODE_REPLACE) as Texture2D
	if tex == null:
		push_error("Custom Tiles: failed to load atlas texture")
		return

	var atlas: TileSetAtlasSource
	if tileset.has_source(SOURCE_ID):
		atlas = tileset.get_source(SOURCE_ID) as TileSetAtlasSource
	else:
		atlas = TileSetAtlasSource.new()
		tileset.add_source(atlas, SOURCE_ID)
		changed = true
	# Nudging texture through null forces the editor's tile preview to refresh
	# even when the new texture has the same resource_path as the old one.
	if atlas_rewritten or atlas.texture != tex:
		atlas.texture = null
		atlas.texture = tex
		changed = true
	if atlas.texture_region_size != tile_size:
		atlas.texture_region_size = tile_size
		changed = true

	# Reconcile tile entries against the set of present indices.
	var present_coords: Dictionary = {}
	for idx in present.keys():
		present_coords[_coord_for(int(idx))] = true

	var to_remove: Array[Vector2i] = []
	for j in atlas.get_tiles_count():
		var c := atlas.get_tile_id(j)
		if not present_coords.has(c):
			to_remove.append(c)
	for c in to_remove:
		atlas.remove_tile(c)
		changed = true

	var phys := tileset.get_physics_layers_count()
	var poly := _full_cell_polygon(tile_size)
	for coord_v in present_coords.keys():
		var coord: Vector2i = coord_v
		if not atlas.has_tile(coord):
			atlas.create_tile(coord)
			var data := atlas.get_tile_data(coord, 0)
			for layer in phys:
				data.add_collision_polygon(layer)
				data.set_collision_polygon_points(layer, 0, poly)
			changed = true

	if changed:
		var err := ResourceSaver.save(tileset, TILESET_PATH)
		if err != OK:
			push_error("Custom Tiles: failed to save tileset (%s)" % err)
	print("Custom Tiles: %d tile(s) live across %d slot(s)" % [present.size(), max_index + 1])

func _full_cell_polygon(tile_size: Vector2i) -> PackedVector2Array:
	var half := Vector2(tile_size) * 0.5
	return PackedVector2Array([
		Vector2(-half.x, -half.y),
		Vector2(half.x, -half.y),
		Vector2(half.x, half.y),
		Vector2(-half.x, half.y),
	])

func _coord_for(index: int) -> Vector2i:
	return Vector2i(index % COLS, index / COLS)

func _png_matches(abs_path: String, img: Image) -> bool:
	if not FileAccess.file_exists(abs_path):
		return false
	var existing := Image.load_from_file(abs_path)
	return existing != null \
		and existing.get_size() == img.get_size() \
		and existing.get_data() == img.get_data()

func _list_pngs(dir_path: String) -> Array[String]:
	var out: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return out
	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		if not dir.current_is_dir() and entry.get_extension().to_lower() == "png":
			out.append(dir_path.path_join(entry))
		entry = dir.get_next()
	dir.list_dir_end()
	out.sort()
	return out

func _load_manifest() -> Dictionary:
	if not FileAccess.file_exists(MANIFEST_PATH):
		return {}
	var f := FileAccess.open(MANIFEST_PATH, FileAccess.READ)
	if f == null:
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	var raw_tiles: Dictionary = parsed.get("tiles", {})
	var tiles := {}
	for k in raw_tiles.keys():
		tiles[String(k)] = int(raw_tiles[k])
	return {
		"tiles": tiles,
		"next_index": int(parsed.get("next_index", 0)),
	}

func _save_manifest(manifest: Dictionary) -> void:
	var f := FileAccess.open(MANIFEST_PATH, FileAccess.WRITE)
	if f == null:
		push_error("Custom Tiles: failed to write %s" % MANIFEST_PATH)
		return
	f.store_string(JSON.stringify(manifest, "\t", true))
	f.close()

func _purge_legacy_sources(tileset: TileSet) -> bool:
	# Drop sources from earlier plugin versions: v1 tagged each source with
	# LEGACY_META_KEY; v2 (per-PNG + manifest) didn't, so also catch any
	# source whose texture lives inside TILES_DIR.
	var changed := false
	var to_remove: Array[int] = []
	for i in tileset.get_source_count():
		var sid := tileset.get_source_id(i)
		if sid == SOURCE_ID:
			continue
		var src := tileset.get_source(sid)
		if src == null:
			continue
		var is_legacy := src.has_meta(LEGACY_META_KEY)
		if not is_legacy and src is TileSetAtlasSource:
			var tex: Texture2D = (src as TileSetAtlasSource).texture
			if tex and tex.resource_path.begins_with(TILES_DIR + "/"):
				is_legacy = true
		if is_legacy:
			to_remove.append(sid)
	for sid in to_remove:
		tileset.remove_source(sid)
		changed = true
	return changed
