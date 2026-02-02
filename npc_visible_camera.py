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
    world.set_weather(carla.WeatherParameters.ClearNoon)
    original_settings = world.get_settings()

    # -------- Sync mode --------
    if args.sync:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

    # -------- Pygame window --------
    display = pygame.display.set_mode(
        (args.width, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF
    )
    pygame.display.set_caption("NPC Scenario – Visible Camera View")
    clock = pygame.time.Clock()

    blueprint_library = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()

    # =========================
    # SPAWN NPC VEHICLES
    # =========================
    npc_vehicles = []
    vehicle_bps = blueprint_library.filter("vehicle.*")

    base_spawn = spawn_points[0]

    for i in range(10):
        bp = random.choice(vehicle_bps)
        spawn = spawn_points[i % len(spawn_points)]
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

    cam_transform = carla.Transform(
        carla.Location(
            x=base_spawn.location.x - 2,
            y=base_spawn.location.y - 15,
            z=45
        ),
        carla.Rotation(
            pitch=-30,
            yaw=base_spawn.rotation.yaw
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
    TOTAL_TIME = 30.0
    RED_START = 10.0
    RED_END = 15.0
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
                print("30 seconds completed.")
                break

            # ---- NPC control ----
            if RED_START <= elapsed < RED_END:
                control = carla.VehicleControl(throttle=0.0, brake=1.0)
            else:
                control = carla.VehicleControl(throttle=0.7, brake=0.0)

            for npc in npc_vehicles:
                npc.apply_control(control)

            # ---- Render ----
            if surface is not None:
                display.blit(surface, (0, 0))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

    finally:
        print("Cleaning up...")
        camera.stop()
        camera.destroy()
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
