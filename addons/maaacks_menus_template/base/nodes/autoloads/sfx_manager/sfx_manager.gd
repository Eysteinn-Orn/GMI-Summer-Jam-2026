extends Node

@export var sound_files : Dictionary[String, AudioStream]
## For accessing all sounds of the same key by said key.
@onready var audio_stream_players : Dictionary[String, Array]

## Remove a sound, terminating it's audio.
func remove_sound(instance: AudioStreamPlayer) -> void:
	instance.queue_free()

## Play a sound by it's key. Returns the instance node.
##
## [param sound] references an AudioStream in [member sound_files].
func create_sound(sound: String) -> AudioStreamPlayer:
	var instance = AudioStreamPlayer.new()
	var i : int = 1
	instance.bus = &"SFX"
	if (sound_files.has(sound)): instance.stream = sound_files[sound]
	instance.finished.connect(remove_sound.bind(instance))
	if (!audio_stream_players.has(sound)): audio_stream_players[sound] = [instance]
	else:
		audio_stream_players[sound].push_front(instance)
		i = audio_stream_players[sound].size()
	instance.name = sound + str(i)
	add_child(instance)
	instance.play()
	return instance

## Destroy sound by some key, or all of them if no key is provided.
##
## [param whitelist] destroys all sounds *but* the specified sound if true.
func destroy_sounds(sound: String, whitelist: bool = false) -> void:
	if (!sound or (!audio_stream_players.has(sound) and whitelist)):
		for instance in get_children(): 
			instance.queue_free()
	else: 
		if (!audio_stream_players.has(sound)): return
		if whitelist:
			for instance in get_children(): 
				if (!audio_stream_players[sound].has(instance)): instance.queue_free()
		else:
			for instance in audio_stream_players[sound]: 
				if instance: instance.queue_free()
			audio_stream_players[sound].clear()
