#!/usr/bin/env python3

import argparse
import random
import pygame
import carla


def game_loop(args):

    pygame.init()
    pygame.font.init()

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    world = client.get_world()
    client.load_world("Town03")
    print("Running map:", world.get_map().name)

    original_settings = world.get_settings()

    if args.sync:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

    display = pygame.display.set_mode(
        (args.width, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF
    )
    pygame.display.set_caption("CARLA Drone View")
    clock = pygame.time.Clock()

    blueprint_library = world.get_blueprint_library()

    # =========================
    # SPAWN EGO
    # =========================
    spawn_points = world.get_map().get_spawn_points()
        # spawn_points = world.get_map().get_spawn_points()
    print("Total spawn points:", len(spawn_points))

    for i, sp in enumerate(spawn_points):
        loc = sp.location + carla.Location(z=3.0)   # raise above ground

        world.debug.draw_point(
            loc,
            size=0.3,
            color=carla.Color(0, 0, 255),
            life_time=1000.0,
            persistent_lines=True
        )

        world.debug.draw_string(
            loc,
            str(i),
            draw_shadow=False,
            color=carla.Color(255, 0, 0),
            life_time=1000.0,
            persistent_lines=True
        )

    ego_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
    ego_vehicle = world.spawn_actor(ego_bp, spawn_points[1])
    ego_vehicle.set_autopilot(True)

    # =========================
    # SPAWN ONE NPC
    # =========================
    npc_vehicles = []
    npc_bp = random.choice(blueprint_library.filter("vehicle.*"))
    npc = world.try_spawn_actor(npc_bp, spawn_points[146])
    if npc:
        npc.set_autopilot(True)
        npc_vehicles.append(npc)

    print(f"Ego + {len(npc_vehicles)} NPC vehicles spawned")

    # =========================
    # DRONE CAMERA
    # =========================
    camera_bp = blueprint_library.find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", str(args.width))
    camera_bp.set_attribute("image_size_y", str(args.height))
    camera_bp.set_attribute("fov", "90")

    DRONE_HEIGHT = 60

    camera_transform = carla.Transform(
        carla.Location(
            # x=ego_vehicle.get_location().x,
            # y=ego_vehicle.get_location().y,
            x=0,
            y=0,
            z=DRONE_HEIGHT
        ),
        carla.Rotation(pitch=-90)
    )

    camera = world.spawn_actor(camera_bp, camera_transform)

    surface = None

    def process_image(image):
        nonlocal surface
        image.convert(carla.ColorConverter.Raw)
        surface = pygame.image.frombuffer(
            image.raw_data,
            (image.width, image.height),
            "RGBA"
        ).convert()

    camera.listen(process_image)

    TOTAL_TIME = 20.0
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
                print("Finished 20 seconds.")
                break

            # =========================
            # DRONE FOLLOW EGO
            # =========================
            ego_loc = ego_vehicle.get_location()
            drone_transform = carla.Transform(
                carla.Location(
                    x=ego_loc.x,
                    y=ego_loc.y,
                    z=DRONE_HEIGHT
                ),
                carla.Rotation(pitch=-90)
            )
            camera.set_transform(drone_transform)

            # =========================
            # RENDER
            # =========================
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
