"""A small 3D MMORPG-style prototype. Install with: pip install ursina

Run a multiplayer relay in one terminal with ``python Prac.py --server``;
then start clients with ``python Prac.py --host 127.0.0.1``.
"""
import json
import math
import socket
import sys
import time
import uuid

try:
	from ursina import *
except ImportError:
	print("This game needs Ursina. Install it with: pip install ursina")
	raise SystemExit(1)


PORT = 45871


def run_server():
	"""Tiny UDP state relay for friends playing on the same network."""
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.bind(("0.0.0.0", PORT))
	players = {}
	print(f"Realm relay listening on UDP port {PORT}. Press Ctrl+C to stop.")
	while True:
		data, address = sock.recvfrom(4096)
		try:
			packet = json.loads(data.decode("utf-8"))
			if packet.get("type") != "state":
				continue
			player_id = str(packet["id"])
			players[player_id] = {"id": player_id, "name": str(packet.get("name", "Adventurer"))[:16],
								  "x": float(packet["x"]), "y": float(packet["y"]),
								  "z": float(packet["z"]), "yaw": float(packet["yaw"]),
								  "level": int(packet.get("level", 1)), "address": address,
								  "seen": time.time()}
			now = time.time()
			players = {key: value for key, value in players.items() if now - value["seen"] < 20}
			visible = [{key: value[key] for key in ("id", "name", "x", "y", "z", "yaw", "level")}
					   for key, value in players.items() if key != player_id]
			sock.sendto(json.dumps({"players": visible}).encode("utf-8"), address)
		except (ValueError, KeyError, TypeError, UnicodeDecodeError):
			continue


if "--server" in sys.argv:
	run_server()
	raise SystemExit

host = "127.0.0.1"
if "--host" in sys.argv:
	try:
		host = sys.argv[sys.argv.index("--host") + 1]
	except IndexError:
		print("Usage: python Prac.py --host SERVER_IP")
		raise SystemExit(2)

app = Ursina()
window.title = "Elderglen Online — 3D RPG Prototype"
window.color = color.rgb(112, 167, 205)
window.fps_counter.enabled = True
window.exit_button.visible = False
mouse.locked = True

Sky(color=color.rgb(120, 180, 220))
DirectionalLight(y=10, z=5, rotation=(45, -35, 35), shadows=True)
AmbientLight(color=color.rgba(130, 130, 150, 0.55))

# A roomy field with a path and scattered trees.
ground = Entity(model="plane", scale=150, texture="white_cube", texture_scale=(75, 75),
				color=color.rgb(87, 145, 72), collider="box")
Entity(model="cube", position=(0, .03, 3), scale=(5, .08, 150), color=color.rgb(174, 148, 105))
for i in range(46):
	x = (i * 17 % 73) - 36
	z = (i * 29 % 125) - 62
	if abs(x) < 5:
		x += 8
	Entity(model="cylinder", position=(x, 1.1, z), scale=(.55, 2.2, .55),
		   color=color.rgb(105, 71, 43), collider="box")
	Entity(model="sphere", position=(x, 3.1, z), scale=(2.7, 2.8, 2.7),
		   color=color.rgb(46, 112 + (i % 3) * 8, 58))

player = Entity(position=(0, 0, -8), rotation_y=0)
Entity(parent=player, model="cube", y=1, scale=(.7, 1.4, .45), color=color.azure)
Entity(parent=player, model="sphere", y=1.95, scale=.48, color=color.rgb(240, 192, 150))
Entity(parent=player, model="cube", y=1.12, z=.29, scale=(.2, .16, .08), color=color.rgb(55, 40, 30))

camera.position = (0, 5, -15)
camera.fov = 80

town_npc = Entity(model="cube", position=(0, 0, 4), scale=(.8, 1.7, .6), color=color.gold,
				  collider="box")
Entity(model="sphere", position=(0, 2, 4), scale=.48, color=color.rgb(230, 185, 142))
Text("Elder Mira  [E]", position=(-.11, .39), scale=1.1, billboard=True, color=color.white)

hud = Text("", position=(-.86, .45), scale=1.05, background=True)
notice = Text("", origin=(0, 0), y=.34, scale=1.5, color=color.yellow)
help_text = Text("WASD move | Mouse look | Left-click attack | E talk/quest | Esc unlock mouse",
				 position=(-.86, -.47), scale=.85, background=True)
chat = Text("Realm: connecting…", position=(-.86, -.41), scale=.85, color=color.azure)

level = 1
xp = 0
xp_next = 30
health = 100
quest_active = False
quest_kills = 0
quest_done = False
attack_timer = 0
message_timer = 0
player_id = str(uuid.uuid4())
player_name = "Adventurer-" + player_id[:4]
remote_players = {}
last_net_send = 0
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)


class Wolf(Entity):
	def __init__(self, pos):
		super().__init__(model="cube", position=pos, scale=(.9, .65, 1.25),
						 color=color.rgb(119, 119, 133), collider="box")
		self.hp = 2
		self.walk = random.uniform(0, math.tau)
		self.attack_cooldown = 0
		self.name_tag = Text("Forest Wolf", parent=self, y=1.2, scale=5, billboard=True,
							 color=color.white)

	def update(self):
		self.attack_cooldown -= time.dt
		delta = player.position - self.position
		distance = math.sqrt(delta.x * delta.x + delta.z * delta.z)
		if distance < 14 and distance > 1.45:
			self.position += Vec3(delta.x, 0, delta.z).normalized() * time.dt * 1.15
			self.rotation_y = math.degrees(math.atan2(delta.x, delta.z))
		elif distance <= 1.45 and self.attack_cooldown <= 0:
			damage_player(7)
			self.attack_cooldown = 1.5
		else:
			self.walk += time.dt
			self.x += math.sin(self.walk) * time.dt * .22


wolves = [Wolf((random.uniform(-25, 25), .45, random.uniform(12, 52))) for _ in range(10)]


def show_notice(message, duration=2.5):
	global message_timer
	notice.text = message
	message_timer = duration


def damage_player(amount):
	global health
	health = max(0, health - amount)
	if health <= 0:
		health = 100
		player.position = (0, 0, -8)
		show_notice("You were defeated. Mira restored you.")


def gain_xp(amount):
	global xp, level, xp_next
	xp += amount
	while xp >= xp_next:
		xp -= xp_next
		level += 1
		xp_next = int(xp_next * 1.45)
		show_notice(f"Level up! You are now level {level}.", 3)


def attack():
	global attack_timer, quest_kills, quest_done
	if attack_timer > 0:
		return
	attack_timer = .55
	targets = [wolf for wolf in wolves if wolf.enabled and distance(player, wolf) < 3.3]
	if not targets:
		show_notice("No enemy in range.", .8)
		return
	target = min(targets, key=lambda wolf: distance(player, wolf))
	target.hp -= 1
	target.color = color.rgb(210, 80, 75)
	invoke(setattr, target, "color", color.rgb(119, 119, 133), delay=.15)
	if target.hp <= 0:
		target.enabled = False
		gain_xp(12)
		if quest_active and not quest_done:
			quest_kills += 1
			if quest_kills >= 5:
				quest_done = True
				gain_xp(40)
				show_notice("Quest complete! Return to Elder Mira.", 4)
			else:
				show_notice(f"Wolf defeated — quest progress {quest_kills}/5.")
		else:
			show_notice("Wolf defeated! +12 XP.")
		invoke(respawn_wolf, target, delay=8)


def respawn_wolf(wolf):
	wolf.position = (random.uniform(-25, 25), .45, random.uniform(12, 52))
	wolf.hp = 2
	wolf.enabled = True


def talk_to_elder():
	global quest_active, quest_done, quest_kills, health
	if distance(player, town_npc) > 4:
		show_notice("Get closer to Elder Mira.")
	elif quest_done:
		quest_done = False
		quest_active = False
		quest_kills = 0
		health = 100
		show_notice("Mira: Well done, hero! Your health is restored. (Quest complete)", 4)
	elif not quest_active:
		quest_active = True
		quest_kills = 0
		show_notice("Mira: Defeat 5 forest wolves, then return to me!", 4)
	else:
		show_notice(f"Mira: The forest wolves await. ({quest_kills}/5)", 3)


def input(key):
	if key == "left mouse down":
		attack()
	elif key == "e":
		talk_to_elder()
	elif key == "escape":
		mouse.locked = not mouse.locked


def network_update():
	global last_net_send
	now = time.time()
	if now - last_net_send >= .12:
		packet = {"type": "state", "id": player_id, "name": player_name,
				  "x": player.x, "y": player.y, "z": player.z,
				  "yaw": player.rotation_y, "level": level}
		try:
			sock.sendto(json.dumps(packet).encode("utf-8"), (host, PORT))
		except OSError:
			pass
		last_net_send = now
	while True:
		try:
			data, _ = sock.recvfrom(8192)
			packet = json.loads(data.decode("utf-8"))
			for remote in packet.get("players", []):
				if remote["id"] == player_id:
					continue
				entity = remote_players.get(remote["id"])
				if entity is None:
					entity = Entity(model="cube", scale=(.7, 1.4, .45), color=color.cyan)
					Entity(parent=entity, model="sphere", y=.83, scale=.68, color=color.rgb(240, 192, 150))
					entity.tag = Text(remote.get("name", "Adventurer"), parent=entity, y=1.35,
									  scale=7, billboard=True, color=color.white)
					remote_players[remote["id"]] = entity
				entity.position = (remote["x"], remote["y"] + .7, remote["z"])
				entity.rotation_y = remote["yaw"]
				entity.tag.text = f"{remote.get('name', 'Adventurer')} Lv.{remote.get('level', 1)}"
			chat.text = f"Realm: {host}:{PORT} | You: {player_name}"
		except BlockingIOError:
			break
		except (OSError, ValueError, KeyError):
			break


def update():
	global attack_timer, message_timer
	dt = time.dt
	if mouse.locked:
		player.rotation_y += mouse.velocity[0] * 100
		forward = (held_keys["w"] - held_keys["s"])
		sideways = (held_keys["d"] - held_keys["a"])
		move = (player.forward * forward + player.right * sideways)
		if move.length() > 0:
			player.position += move.normalized() * dt * 6
	player.x = clamp(player.x, -68, 68)
	player.z = clamp(player.z, -68, 68)
	camera.position = lerp(camera.position, player.position + Vec3(0, 5, -10) * player.forward.z + Vec3(0, 0, 0), dt * 4)
	# Keep the camera behind the character, including while turning.
	camera.position = lerp(camera.position, player.position - player.forward * 10 + Vec3(0, 5, 0), dt * 5)
	camera.look_at(player.position + Vec3(0, 1.2, 0))
	attack_timer = max(0, attack_timer - dt)
	if message_timer > 0:
		message_timer -= dt
		if message_timer <= 0:
			notice.text = ""
	quest_line = f"Quest: Wolves {quest_kills}/5" if quest_active and not quest_done else (
		"Quest: Return to Elder Mira" if quest_done else "Quest: Talk to Elder Mira [E]")
	hud.text = f"Lv. {level}   HP {health}/100   XP {xp}/{xp_next}\n{quest_line}"
	network_update()


app.run()
