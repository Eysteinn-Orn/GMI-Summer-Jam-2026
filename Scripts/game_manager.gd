extends Node

@onready var eclipse_timer: Timer = %EclipseTimer

func _ready():
    eclipse_timer.timeout.connect(_on_eclipse_timer_timeout)


func _on_eclipse_timer_timeout(): #Game over when the timer runs out, but you can change this to do something else if you want.
    pass