import argparse
import random
import pygame
import carla
import numpy as np

def game_loop(args):
    pygame.init()
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    world = client.load_world("Town03")
    original_settings = world.get_settings()

    if args.sync:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

    display = pygame.display.set_mode((args.width * 2, args.height), pygame.HWSURFACE | pygame.DOUBLEBUF)
    clock = pygame.time.Clock()

    # =========================
    # SPAWN EGO
    # =========================

    blueprint_library = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()

    # =========================
    # WAYPOINTS
    # =========================
    waypoints = world.get_map().generate_waypoints(2.0)
    junction_waypoints = [w for w in waypoints if w.is_junction]

    count = 0
    for w in junction_waypoints:
        w.transform.location
        count += 1
        print(count, w.transform.location, w.transform.rotation)

    ego_bp_v = blueprint_library.filter("vehicle.tesla.model3")[0]
    ego_vehicle = world.spawn_actor(ego_bp_v, spawn_points[1])
    ego_vehicle.set_autopilot(True)


    # =========================
    # SPAWN NPC
    # =========================

    npc_vehicles = []

    npc_index = 20
    npc_bp = random.choice(blueprint_library.filter("vehicle.*"))

    npc = world.try_spawn_actor(npc_bp, spawn_points[npc_index])
    if npc:
        npc.set_autopilot(False)
        npc_vehicles.append(npc)

    print(f"Ego + {len(npc_vehicles)} NPC vehicles spawned")

    # =========================
    # SPAWN NEW POINT
    # =========================

    new_location = carla.Location(x=231.270920, y=0.265452-20, z=0.275307)
    new_rotation = carla.Rotation(pitch = 0.0, yaw=95.0, roll = 0.0)
    new_spawn_point = carla.Transform(new_location, new_rotation)

    new_bp = random.choice(blueprint_library.filter("vehicle.*"))
    new_npc = world.try_spawn_actor(new_bp, new_spawn_point) #spawn_points

    if new_npc:
        npc.set_autopilot(False)
        print("New vehicle spawned")
    else:
        print("Spawn failed. Is the point blocked or underground?")

    # --- Sensor Surfaces ---
    # We use a dictionary or a list to keep references mutable inside callbacks
    shared_data = {'ego_surface': None, 'drone_surface': None}

    def on_ego_image(image):
        image.convert(carla.ColorConverter.Raw)
        array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
        array = np.reshape(array, (image.height, image.width, 4))
        array = array[:, :, :3]
        array = array[:, :, ::-1]
        shared_data['ego_surface'] = pygame.surfarray.make_surface(array.swapaxes(0, 1))

    def on_drone_image(image):
        image.convert(carla.ColorConverter.Raw)
        array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
        array = np.reshape(array, (image.height, image.width, 4))
        array = array[:, :, :3]
        array = array[:, :, ::-1]
        shared_data['drone_surface'] = pygame.surfarray.make_surface(array.swapaxes(0, 1))

    # --- Camera Setup ---
    cam_bp = blueprint_library.find("sensor.camera.rgb")
    cam_bp.set_attribute("image_size_x", str(args.width))
    cam_bp.set_attribute("image_size_y", str(args.height))

    # Ego Camera (Attached)
    ego_cam = world.spawn_actor(
        cam_bp, 
        carla.Transform(carla.Location(x=-6, z=2.5), carla.Rotation(pitch=-15)),
        attach_to=ego_vehicle
    )
    ego_cam.listen(on_ego_image)

    # Drone Camera (Floating)
    drone_cam = world.spawn_actor(
        cam_bp,
        carla.Transform(carla.Location(z=80), carla.Rotation(pitch=-90))
    )
    drone_cam.listen(on_drone_image)

    start_time = None
    running = True

    try:
        while True:
            if args.sync: world.tick()
            else: world.wait_for_tick()

            # Update Drone Position
            ego_loc = ego_vehicle.get_location()
            drone_cam.set_transform(carla.Transform(
                carla.Location(x=ego_loc.x, y=ego_loc.y, z=80),
                carla.Rotation(pitch=-90)
            ))

            # Rendering
            if shared_data['drone_surface']:
                display.blit(shared_data['drone_surface'], (0, 0))
            if shared_data['ego_surface']:
                display.blit(shared_data['ego_surface'], (args.width, 0))

            pygame.display.flip()
            clock.tick(60)

            control = carla.VehicleControl(throttle=0.8, brake=0.0)
            npc.apply_control(control)

            new_npc_start_time = 13.0

            sim_time = world.get_snapshot().timestamp.elapsed_seconds
            if start_time is None:
                start_time = sim_time

            elapsed = sim_time - start_time

            if elapsed < new_npc_start_time:
                control = carla.VehicleControl(throttle=0.0, brake=1.0)
                new_npc.apply_control(control)
            else: 
                control = carla.VehicleControl(throttle=0.5, brake=0.0) 
                new_npc.apply_control(control)

            for event in pygame.event.get():
                if event.type == pygame.QUIT: return

    finally:
        # Proper Cleanup
        ego_cam.stop()
        drone_cam.stop()
        ego_vehicle.destroy()
        world.apply_settings(original_settings)
        pygame.quit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--res", default="640x480")

    args = parser.parse_args()
    args.width, args.height = map(int, args.res.split("x"))

    game_loop(args)


if __name__ == "__main__":
    main()
