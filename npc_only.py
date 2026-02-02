#!/usr/bin/env python3

import argparse
import random
import pygame
import carla

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

    # --- Pygame window ---
    display = pygame.display.set_mode(
        (args.width, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF
    )
    pygame.display.set_caption("CARLA NPC-only 20s Scenario")
    clock = pygame.time.Clock()

    blueprint_library = world.get_blueprint_library()
    spawn_points = world.get_map().get_spawn_points()

    # =========================
    # SPAWN NPC VEHICLES
    # =========================
    npc_vehicles = []
    npc_blueprints = blueprint_library.filter("vehicle.*")

    for i in range(6):  # spawn 6 NPCs
        bp = random.choice(npc_blueprints)
        spawn = spawn_points[i % len(spawn_points)]
        npc = world.try_spawn_actor(bp, spawn)
        if npc:
            npc.set_autopilot(False)
            npc_vehicles.append(npc)

    print(f"{len(npc_vehicles)} NPC vehicles spawned")

    # =========================
    # FIXED CAMERA (SPECTATOR)
    # =========================
    spectator = world.get_spectator()

    cam_transform = carla.Transform(
        carla.Location(x=0, y=0, z=50),
        carla.Rotation(pitch=-90)
    )
    spectator.set_transform(cam_transform)

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

            # ---- EXIT after 20s ----
            if elapsed >= TOTAL_TIME:
                print("20 seconds completed. Exiting.")
                break

            # ---- CONTROL NPCs ----
            if RED_START <= elapsed < RED_END:
                control = carla.VehicleControl(throttle=0.0, brake=1.0)
            else:
                control = carla.VehicleControl(throttle=0.5, brake=0.0)

            for npc in npc_vehicles:
                npc.apply_control(control)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

    finally:
        print("Cleaning up actors...")
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
    parser.add_argument("--res", default="1280x720")

    args = parser.parse_args()
    args.width, args.height = [int(x) for x in args.res.split("x")]

    game_loop(args)


if __name__ == "__main__":
    main()
