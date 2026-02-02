#!/usr/bin/env python3

import carla
import pygame
import argparse
import random
import time
import numpy as np


# ===============================
# Utils
# ===============================
def spawn_vehicle_safe(world, blueprint, spawn_points, tries=40):
    random.shuffle(spawn_points)
    for i in range(min(tries, len(spawn_points))):
        v = world.try_spawn_actor(blueprint, spawn_points[i])
        if v:
            return v, spawn_points[i]
    return None, None


# ===============================
# Scenario
# ===============================
def run_scenario(args):

    pygame.init()
    display = pygame.display.set_mode((args.width * 2, args.height))
    pygame.display.set_caption("Bird-eye (Left) | Ego Camera (Right)")
    clock = pygame.time.Clock()

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    world = client.get_world()

    original_settings = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)

    tm = client.get_trafficmanager(8000)
    tm.set_synchronous_mode(True)

    blueprint_library = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()

    actors = []

    ego_surface = None
    bird_surface = None

    try:
        # =========================
        # EGO VEHICLE
        # =========================
        ego_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
        ego_vehicle, ego_spawn = spawn_vehicle_safe(world, ego_bp, spawn_points)
        if ego_vehicle is None:
            raise RuntimeError("Failed to spawn ego vehicle")

        ego_vehicle.set_autopilot(True, tm.get_port())
        actors.append(ego_vehicle)

        # =========================
        # NPC VEHICLE
        # =========================
        npc_bp = blueprint_library.filter("vehicle.audi.a2")[0]
        npc, _ = spawn_vehicle_safe(world, npc_bp, spawn_points)
        if npc:
            npc.set_autopilot(True, tm.get_port())
            actors.append(npc)

        print("✅ Vehicles spawned")

        # =========================
        # EGO CAMERA
        # =========================
        ego_cam_bp = blueprint_library.find("sensor.camera.rgb")
        ego_cam_bp.set_attribute("image_size_x", str(args.width))
        ego_cam_bp.set_attribute("image_size_y", str(args.height))
        ego_cam_bp.set_attribute("fov", "90")

        ego_cam = world.spawn_actor(
            ego_cam_bp,
            carla.Transform(
                carla.Location(x=-6, z=2.4),
                carla.Rotation(pitch=-15)
            ),
            attach_to=ego_vehicle
        )
        actors.append(ego_cam)

        def ego_cb(image):
            nonlocal ego_surface
            arr = np.frombuffer(image.raw_data, dtype=np.uint8)
            arr = arr.reshape((image.height, image.width, 4))
            ego_surface = pygame.surfarray.make_surface(
                arr[:, :, :3][:, :, ::-1].swapaxes(0, 1)
            )

        ego_cam.listen(ego_cb)

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
                    x=ego_spawn.location.x,
                    y=ego_spawn.location.y - 20,
                    z=45
                ),
                carla.Rotation(pitch=-35)
            )
        )
        actors.append(bird_cam)

        def bird_cb(image):
            nonlocal bird_surface
            arr = np.frombuffer(image.raw_data, dtype=np.uint8)
            arr = arr.reshape((image.height, image.width, 4))
            bird_surface = pygame.surfarray.make_surface(
                arr[:, :, :3][:, :, ::-1].swapaxes(0, 1)
            )

        bird_cam.listen(bird_cb)

        # =========================
        # MAIN LOOP
        # =========================
        start = time.time()
        RUN_TIME = 30.0

        while True:
            clock.tick(20)
            world.tick()

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return

            if bird_surface:
                display.blit(bird_surface, (0, 0))
            if ego_surface:
                display.blit(ego_surface, (args.width, 0))

            pygame.display.flip()

            if time.time() - start > RUN_TIME:
                break

        print("🟢 Scenario finished")

    finally:
        print("🧹 Cleaning up")

        for a in actors:
            if isinstance(a, carla.Sensor):
                a.stop()

        for a in actors:
            if a.is_alive:
                a.destroy()

        world.apply_settings(original_settings)
        pygame.quit()


# ===============================
# Main
# ===============================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    run_scenario(args)


if __name__ == "__main__":
    main()
