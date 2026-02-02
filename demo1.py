#!/usr/bin/env python3

import argparse
import random
import pygame
import carla

# =========================
# MAIN GAME LOOP
# =========================
def game_loop(args):

    pygame.init()
    pygame.font.init()

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    world = client.get_world()
    original_settings = world.get_settings()

    # --- Sync mode ---
    if args.sync:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

    # --- Pygame window ---
    display = pygame.display.set_mode(
        (args.width, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF
    )
    pygame.display.set_caption("CARLA 20s Traffic Signal Scenario")

    clock = pygame.time.Clock()

    # --- Spawn ego vehicle ---
    blueprint_library = world.get_blueprint_library()
    ego_bp = blueprint_library.filter("vehicle.tesla.model3")[0]

    spawn_points = world.get_map().get_spawn_points()
    spawn_point = random.choice(spawn_points)

    ego_vehicle = world.spawn_actor(ego_bp, spawn_point)
    ego_vehicle.set_autopilot(False)

    # --- Camera ---
    camera_bp = blueprint_library.find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", str(args.width))
    camera_bp.set_attribute("image_size_y", str(args.height))
    camera_transform = carla.Transform(
        carla.Location(x=-5.5, z=2.5),
        carla.Rotation(pitch=-15)
    )
    camera = world.spawn_actor(
        camera_bp, camera_transform, attach_to=ego_vehicle
    )

    surface = None

    def process_image(image):
        nonlocal surface
        array = image.raw_data
        image.convert(carla.ColorConverter.Raw)
        array = memoryview(image.raw_data)
        img = pygame.image.frombuffer(array, (image.width, image.height), "RGBA")
        surface = img.convert()

    camera.listen(process_image)

    # --- Timing ---
    TOTAL_TIME = 20.0
    RED_START = 5.0
    RED_END = 10.0

    start_time = None
    running = True

    try:
        while running:
            clock.tick(60)

            if args.sync:
                world.tick()
            else:
                world.wait_for_tick()

            sim_time = world.get_snapshot().timestamp.elapsed_seconds
            if start_time is None:
                start_time = sim_time

            elapsed = sim_time - start_time

            # ---- EXIT after 20 seconds ----
            if elapsed >= TOTAL_TIME:
                print("20 seconds completed. Exiting.")
                break

            # ---- Control logic ----
            if RED_START <= elapsed < RED_END:
                control = carla.VehicleControl(throttle=0.0, brake=1.0)
            else:
                control = carla.VehicleControl(throttle=0.6, brake=0.0)

            ego_vehicle.apply_control(control)

            # ---- Render ----
            if surface is not None:
                display.blit(surface, (0, 0))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

    finally:
        print("Cleaning up actors...")
        camera.stop()
        camera.destroy()
        ego_vehicle.destroy()
        world.apply_settings(original_settings)
        pygame.quit()


# =========================
# MAIN
# =========================
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
