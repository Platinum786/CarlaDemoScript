#!/usr/bin/env python3

import argparse
import random
import pygame
import carla
import numpy as np
import csv

# =========================
# GAME LOOP
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

    blueprint_library = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()

    # --- ONE WINDOW, DOUBLE WIDTH ---
    display = pygame.display.set_mode(
        (args.width * 2, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF
    )
    pygame.display.set_caption("Left: Bird-eye | Right: Ego Camera")
    clock = pygame.time.Clock()

    # =========================
    # SPAWN EGO VEHICLE
    # =========================
    ego_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
    ego_spawn = random.choice(spawn_points)
    ego_vehicle = world.spawn_actor(ego_bp, ego_spawn)
    ego_vehicle.set_autopilot(True)

    # =========================
    # SPAWN NPC VEHICLES
    # =========================
    npc_vehicles = []
    npc_blueprints = blueprint_library.filter("vehicle.*")

    for i in range(10):
        bp = random.choice(npc_blueprints)
        spawn = spawn_points[(i + 1) % len(spawn_points)]
        npc = world.try_spawn_actor(bp, spawn)
        if npc:
            npc.set_autopilot(False)
            npc_vehicles.append(npc)

    print(f"Ego + {len(npc_vehicles)} NPC vehicles spawned")

    # =========================
    # EGO CAMERA
    # =========================
    ego_cam_bp = blueprint_library.find("sensor.camera.rgb")
    ego_cam_bp.set_attribute("image_size_x", str(args.width))
    ego_cam_bp.set_attribute("image_size_y", str(args.height))
    ego_cam_bp.set_attribute("fov", "90")

    ego_cam = world.spawn_actor(
        ego_cam_bp,
        carla.Transform(carla.Location(x=-6, z=2.4),
                        carla.Rotation(pitch=-15)),
        attach_to=ego_vehicle
    )

    ego_surface = None

    def ego_callback(image):
        nonlocal ego_surface
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        ego_surface = pygame.surfarray.make_surface(
            array[:, :, :3][:, :, ::-1].swapaxes(0, 1)
        )

    ego_cam.listen(ego_callback)

    # =========================
    # BIRD-EYE CAMERA
    # =========================
    bird_cam_bp = blueprint_library.find("sensor.camera.rgb")
    bird_cam_bp.set_attribute("image_size_x", str(args.width))
    bird_cam_bp.set_attribute("image_size_y", str(args.height))
    bird_cam_bp.set_attribute("fov", "90")

    bird_cam = world.spawn_actor(
        bird_cam_bp,
        carla.Transform(
            carla.Location(
                x=ego_spawn.location.x - 2,
                y=ego_spawn.location.y - 15,
                z=45
            ),
            carla.Rotation(pitch=-30)
        )
    )

    bird_surface = None

    def bird_callback(image):
        nonlocal bird_surface
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = array.reshape((image.height, image.width, 4))
        bird_surface = pygame.surfarray.make_surface(
            array[:, :, :3][:, :, ::-1].swapaxes(0, 1)
        )

    bird_cam.listen(bird_callback)

    # =========================
    # TIMING & TRAJECTORY
    # =========================
    TOTAL_TIME = 45.0
    RED_START = 10.0
    RED_END = 15.0

    start_time = None
    prev_ego_location = None
    ego_trajectory = []

    try:
        while True:
            clock.tick(60)

            world.tick()

            sim_time = world.get_snapshot().timestamp.elapsed_seconds
            if start_time is None:
                start_time = sim_time

            elapsed = sim_time - start_time
            if elapsed >= TOTAL_TIME:
                print("Scenario finished.")
                break

            # ---- NPC CONTROL ----
            if RED_START <= elapsed < RED_END:
                control = carla.VehicleControl(throttle=0.0, brake=1.0)
            else:
                control = carla.VehicleControl(throttle=0.7)

            for npc in npc_vehicles:
                npc.apply_control(control)

            # ---- EGO TRAJECTORY (VISUAL) ----
            ego_loc = ego_vehicle.get_location()

            if prev_ego_location is not None:
                world.debug.draw_line(
                    prev_ego_location,
                    ego_loc,
                    thickness=0.1,
                    color=carla.Color(255, 0, 0),
                    life_time=20.0
                )

            prev_ego_location = ego_loc

            # ---- EGO TRAJECTORY (CSV DATA) ----
            transform = ego_vehicle.get_transform()
            velocity = ego_vehicle.get_velocity()
            speed = (velocity.x**2 + velocity.y**2 + velocity.z**2) ** 0.5

            ego_trajectory.append({
                "time": elapsed,
                "x": transform.location.x,
                "y": transform.location.y,
                "z": transform.location.z,
                "speed": speed,
                "yaw": transform.rotation.yaw
            })

            # ---- RENDER ----
            if bird_surface:
                display.blit(bird_surface, (0, 0))
            if ego_surface:
                display.blit(ego_surface, (args.width, 0))

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

    finally:
        # =========================
        # SAVE CSV
        # =========================
        with open("ego_trajectory.csv", "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["time", "x", "y", "z", "speed", "yaw"]
            )
            writer.writeheader()
            writer.writerows(ego_trajectory)

        print("Ego trajectory saved to ego_trajectory.csv")

        # =========================
        # CLEANUP
        # =========================
        ego_cam.destroy()
        bird_cam.destroy()
        ego_vehicle.destroy()
        for npc in npc_vehicles:
            npc.destroy()

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
    parser.add_argument("--res", default="640x480")

    args = parser.parse_args()
    args.width, args.height = [int(x) for x in args.res.split("x")]

    game_loop(args)


if __name__ == "__main__":
    main()
