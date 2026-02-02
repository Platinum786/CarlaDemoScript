#!/usr/bin/env python3

import argparse
import random
import pygame
import carla
import numpy as np

def game_loop(args):

    pygame.init()
    pygame.font.init()

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    world = client.get_world()
    original_settings = world.get_settings()

    # -------- Force clear weather --------
    world.set_weather(carla.WeatherParameters.ClearNoon)

    # -------- Sync mode --------
    if args.sync:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

    traffic_manager = client.get_trafficmanager()
    traffic_manager.set_synchronous_mode(args.sync)

    # -------- Pygame window --------
    display = pygame.display.set_mode(
        (args.width, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF
    )
    pygame.display.set_caption("Ego Autopilot + NPC Scenario (20s)")
    clock = pygame.time.Clock()

    blueprint_library = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()

    # =========================
    # SPAWN EGO VEHICLE (AUTOPILOT)
    # =========================
    ego_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
    ego_spawn = random.choice(spawn_points)
    ego_vehicle = world.spawn_actor(ego_bp, ego_spawn)

    ego_vehicle.set_autopilot(True, traffic_manager.get_port())
    print("Ego vehicle spawned (AUTOPILOT ON)")

    # =========================
    # SPAWN NPC VEHICLES
    # =========================
    npc_vehicles = []
    vehicle_bps = blueprint_library.filter("vehicle.*")

    for i in range(6):
        bp = random.choice(vehicle_bps)
        spawn = spawn_points[(i + 1) % len(spawn_points)]
        npc = world.try_spawn_actor(bp, spawn)
        if npc:
            npc.set_autopilot(False)
            npc_vehicles.append(npc)

    print(f"{len(npc_vehicles)} NPC vehicles spawned")

    # =========================
    # CAMERA (ELEVATED + ANGLED)
    # =========================
    camera_bp = blueprint_library.find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", str(args.width))
    camera_bp.set_attribute("image_size_y", str(args.height))
    camera_bp.set_attribute("fov", "90")

    base_loc = ego_spawn.location

    cam_transform = carla.Transform(
        carla.Location(
            x=base_loc.x - 15,
            y=base_loc.y - 20,
            z=25
        ),
        carla.Rotation(
            pitch=-40,
            yaw=ego_spawn.rotation.yaw
        )
    )

    camera = world.spawn_actor(camera_bp, cam_transform)
    surface = None

    def camera_callback(image):
        nonlocal surface
        image.convert(carla.ColorConverter.Raw)
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = np.reshape(array, (image.height, image.width, 4))
        array = array[:, :, :3][:, :, ::-1]
        surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))

    camera.listen(camera_callback)

    # =========================
    # TIMING
    # =========================
    TOTAL_TIME = 20.0
    RED_START = 5.0
    RED_END = 10.0
    start_time = None

    try:
        while True:
            clock.tick(60)

            if args.sync:
                world.tick()
            else:
                world.wait_for_tick()

            sim_time = world.get_snapshot().timestamp.elapsed_seconds
            if start_time is None:
                start_time = sim_time

            elapsed = sim_time - start_time

            if elapsed >= TOTAL_TIME:
                print("20 seconds completed.")
                break

            # ---- NPC control (manual) ----
            if RED_START <= elapsed < RED_END:
                npc_control = carla.VehicleControl(throttle=0.0, brake=1.0)
            else:
                npc_control = carla.VehicleControl(throttle=0.5, brake=0.0)

            for npc in npc_vehicles:
                npc.apply_control(npc_control)

            # ---- Render ----
            if surface is not None:
                display.blit(surface, (0, 0))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

    finally:
        print("Cleaning up actors...")
        camera.stop()
        camera.destroy()
        ego_vehicle.destroy()
        for npc in npc_vehicles:
            npc.destroy()

        world.apply_settings(original_settings)
        pygame.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--res", default="1280x720")

    args = parser.parse_args()
    args.width, args.height = [int(x) for x in args.res.split("x")]

    game_loop(args)


if __name__ == "__main__":
    main()
