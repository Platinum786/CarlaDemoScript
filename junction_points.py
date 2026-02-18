#!/usr/bin/env python3

import argparse
import pygame
import carla
import numpy as np


# =========================
# CAMERA INTRINSIC MATRIX
# =========================
def get_intrinsic_matrix(width, height, fov):
    focal = width / (2.0 * np.tan(np.radians(fov) / 2))
    K = np.identity(3)
    K[0, 0] = focal
    K[1, 1] = focal
    K[0, 2] = width / 2.0
    K[1, 2] = height / 2.0
    return K


# =========================
# WORLD → IMAGE PROJECTION
# =========================
def project_world_to_image(world_location, camera, K):

    world_2_camera = np.array(camera.get_transform().get_inverse_matrix())

    point = np.array([world_location.x,
                      world_location.y,
                      world_location.z,
                      1.0])

    point_camera = world_2_camera @ point

    # UE4 → conventional camera coordinates
    point_camera = np.array([
        point_camera[1],
        -point_camera[2],
        point_camera[0]
    ])

    if point_camera[2] <= 0:
        return None

    point_img = K @ point_camera
    point_img /= point_img[2]

    return int(point_img[0]), int(point_img[1])


# =========================
# GET ALL JUNCTION CENTERS
# =========================
def get_junction_centers(world):

    carla_map = world.get_map()
    topology = carla_map.get_topology()

    junction_dict = {}

    for wp_start, wp_end in topology:

        if wp_start.is_junction:
            junction = wp_start.get_junction()
            jid = junction.id

            if jid not in junction_dict:
                junction_dict[jid] = []

            junction_dict[jid].append(wp_start.transform.location)

    # Compute geometric center of each junction
    centers = []

    for jid, locs in junction_dict.items():
        xs = [l.x for l in locs]
        ys = [l.y for l in locs]
        zs = [l.z for l in locs]

        center = carla.Location(
            x=sum(xs) / len(xs),
            y=sum(ys) / len(ys),
            z=sum(zs) / len(zs)
        )

        centers.append((jid, center))

    return centers


# =========================
# MAIN
# =========================
def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--res", default="1280x720")
    args = parser.parse_args()

    width, height = [int(x) for x in args.res.split("x")]

    pygame.init()
    display = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Junction Overlay")
    font = pygame.font.SysFont("Arial", 16)

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    world = client.load_world("Town03")
    blueprint_library = world.get_blueprint_library()

    # =========================
    # GET JUNCTION CENTERS
    # =========================
    junctions = get_junction_centers(world)
    print("Total junctions:", len(junctions))

    for idx, (jid, loc) in enumerate(junctions):
        print(idx, "Junction ID:", jid, loc)

    # =========================
    # SPAWN EGO
    # =========================
    spawn_points = world.get_map().get_spawn_points()
    ego_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
    ego_vehicle = world.spawn_actor(ego_bp, spawn_points[1])
    ego_vehicle.set_autopilot(True)

    # =========================
    # DRONE CAMERA
    # =========================
    camera_bp = blueprint_library.find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", str(width))
    camera_bp.set_attribute("image_size_y", str(height))
    camera_bp.set_attribute("fov", "90")

    DRONE_HEIGHT = 90

    camera = world.spawn_actor(
        camera_bp,
        carla.Transform(
            carla.Location(z=DRONE_HEIGHT),
            carla.Rotation(pitch=-90)
        )
    )

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

    K = get_intrinsic_matrix(width, height, 90)

    try:
        while True:

            world.wait_for_tick()

            ego_loc = ego_vehicle.get_location()

            camera.set_transform(
                carla.Transform(
                    carla.Location(
                        x=ego_loc.x,
                        y=ego_loc.y,
                        z=DRONE_HEIGHT
                    ),
                    carla.Rotation(pitch=-90)
                )
            )

            if surface is not None:
                display.blit(surface, (0, 0))

                for i, (jid, loc) in enumerate(junctions):

                    loc_draw = loc + carla.Location(z=1.0)
                    pixel = project_world_to_image(loc_draw, camera, K)

                    if pixel is None:
                        continue

                    x, y = pixel

                    if 0 <= x < width and 0 <= y < height:

                        # Draw RED square marker
                        rect = pygame.Rect(x-10, y-10, 20, 20)
                        pygame.draw.rect(display, (200, 0, 0), rect, 3)

                        text = font.render(str(i), True, (255, 255, 255))
                        text_rect = text.get_rect(center=(x, y))
                        display.blit(text, text_rect)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

    finally:
        camera.stop()
        camera.destroy()
        ego_vehicle.destroy()
        pygame.quit()


if __name__ == "__main__":
    main()
