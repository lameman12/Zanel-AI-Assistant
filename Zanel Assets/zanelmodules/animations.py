import threading
import random
import time
import tkinter as tk
import math


_flip_coin_last_time = 0.0


def flip_coin_animation(parent, result_callback=None):
    global _flip_coin_last_time

    now = time.monotonic()

    if now - _flip_coin_last_time < 10:
        remaining = max(
            1,
            math.ceil(
                10 - (
                    now - _flip_coin_last_time
                )
            ),
        )

        try:
            parent.bell()
        except Exception:
            pass

        return (
            f"Coin flip is on cooldown. "
            f"Try again in {remaining} seconds."
        )

    _flip_coin_last_time = now

    width = 430
    height = 285

    window = tk.Toplevel(parent)
    window.withdraw()
    window.overrideredirect(True)
    window.resizable(False, False)
    window.attributes("-topmost", True)
    window.configure(bg="#080a0f")

    try:
        window.attributes(
            "-alpha",
            0.98,
        )
    except Exception:
        pass

    window.update_idletasks()

    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()

    screen_width = parent.winfo_screenwidth()
    screen_height = parent.winfo_screenheight()

    gap = 14

    right_x = (
        parent_x
        + parent_width
        + gap
    )

    left_x = (
        parent_x
        - width
        - gap
    )

    if right_x + width <= screen_width - 8:
        x = right_x
    elif left_x >= 8:
        x = left_x
    else:
        x = max(
            8,
            min(
                parent_x
                + (
                    parent_width
                    - width
                )
                // 2,
                screen_width
                - width
                - 8,
            ),
        )

    y = (
        parent_y
        + (
            parent_height
            - height
        )
        // 2
    )

    y = max(
        8,
        min(
            y,
            screen_height
            - height
            - 8,
        ),
    )

    window.geometry(
        f"{width}x{height}+{x}+{y}"
    )

    drag_data = {
        "x": 0,
        "y": 0,
    }

    def start_drag(event):
        drag_data["x"] = event.x_root
        drag_data["y"] = event.y_root

    def drag_window(event):
        delta_x = (
            event.x_root
            - drag_data["x"]
        )

        delta_y = (
            event.y_root
            - drag_data["y"]
        )

        current_x = window.winfo_x()
        current_y = window.winfo_y()

        new_x = current_x + delta_x
        new_y = current_y + delta_y

        new_x = max(
            4,
            min(
                new_x,
                screen_width
                - width
                - 4,
            ),
        )

        new_y = max(
            4,
            min(
                new_y,
                screen_height
                - height
                - 4,
            ),
        )

        window.geometry(
            f"{width}x{height}+{new_x}+{new_y}"
        )

        drag_data["x"] = event.x_root
        drag_data["y"] = event.y_root

    canvas = tk.Canvas(
        window,
        width=width,
        height=height,
        bg="#080a0f",
        highlightthickness=0,
        bd=0,
    )

    canvas.pack(
        fill="both",
        expand=True,
    )

    canvas.bind(
        "<ButtonPress-1>",
        start_drag,
    )

    canvas.bind(
        "<B1-Motion>",
        drag_window,
    )

    canvas.create_rectangle(
        1,
        1,
        width - 1,
        height - 1,
        fill="#0d1017",
        outline="#252b36",
        width=1,
    )

    canvas.create_rectangle(
        10,
        10,
        width - 10,
        height - 10,
        fill="#0a0d13",
        outline="#171c25",
        width=1,
    )

    canvas.create_line(
        22,
        22,
        width - 22,
        22,
        fill="#252b36",
        width=1,
    )

    canvas.create_text(
        28,
        66,
        text="Zanel",
        anchor="w",
        fill="#d9a441",
        font=(
            "Segoe UI",
            8,
            "bold",
        ),
    )

    canvas.create_text(
        28,
        91,
        text="COIN FLIP",
        anchor="w",
        fill="#ffffff",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    )

    canvas.create_line(
        28,
        112,
        28,
        166,
        fill="#d9a441",
        width=2,
    )

    canvas.create_text(
        28,
        190,
        text="RANDOM",
        anchor="w",
        fill="#687180",
        font=(
            "Segoe UI",
            6,
            "bold",
        ),
    )

    canvas.create_text(
        28,
        205,
        text="The Coolest Animation!",
        anchor="w",
        fill="#3f4652",
        font=(
            "Segoe UI",
            6,
            "bold",
        ),
    )

    result = random.choice(
        (
            "Heads",
            "Tails",
        )
    )

    center_x = 275
    base_y = 130

    frame = 0
    total_frames = 100

    dust_particles = []

    def draw_coin(
        scale_x,
        rotation,
        coin_y,
        alpha_scale=1.0,
    ):
        canvas.delete("coin")

        radius = 68

        visible_width = max(
            2,
            int(
                radius
                * scale_x
            ),
        )

        visible_height = max(
            2,
            int(
                radius
                * alpha_scale
            ),
        )

        left = (
            center_x
            - visible_width
        )

        right = (
            center_x
            + visible_width
        )

        top = (
            coin_y
            - visible_height
        )

        bottom = (
            coin_y
            + visible_height
        )

        canvas.create_oval(
            left + 8,
            top + 10,
            right + 8,
            bottom + 10,
            fill="#020307",
            outline="",
            tags="coin",
        )

        canvas.create_oval(
            left - 4,
            top - 4,
            right + 4,
            bottom + 4,
            fill="#17130a",
            outline="#6f531d",
            width=2,
            tags="coin",
        )

        canvas.create_oval(
            left,
            top,
            right,
            bottom,
            fill="#c89430",
            outline="#f7d879",
            width=3,
            tags="coin",
        )

        if visible_width > 10:
            canvas.create_oval(
                left + 7,
                top + 7,
                right - 7,
                bottom - 7,
                outline="#edc45a",
                width=2,
                tags="coin",
            )

        if scale_x > 0.16:
            label = (
                result
                if rotation == 0
                else "Zanel"
            )

            canvas.create_text(
                center_x,
                coin_y,
                text=label,
                fill="#fff2ad",
                font=(
                    "Segoe UI",
                    max(
                        9,
                        int(
                            19
                            * min(
                                1.0,
                                scale_x
                                + 0.15,
                            )
                        ),
                    ),
                    "bold",
                ),
                tags="coin",
            )

        if scale_x < 0.2:
            edge_width = max(
                5,
                int(
                    radius
                    * 0.16
                ),
            )

            canvas.create_rectangle(
                center_x
                - edge_width,
                top,
                center_x
                + edge_width,
                bottom,
                fill="#986d21",
                outline="#e4ba4d",
                width=2,
                tags="coin",
            )

    def create_coin_particles():
        dust_particles.clear()

        particle_count = 120

        for _ in range(
            particle_count
        ):
            angle = random.uniform(
                0,
                math.pi * 2,
            )

            distance = random.uniform(
                5,
                58,
            )

            x = (
                center_x
                + math.cos(angle)
                * distance
            )

            y = (
                base_y
                + math.sin(angle)
                * distance
            )

            size = random.uniform(
                1.2,
                3.8,
            )

            particle = canvas.create_oval(
                x - size,
                y - size,
                x + size,
                y + size,
                fill=random.choice(
                    (
                        "#d9a441",
                        "#f5d77a",
                        "#9c7024",
                        "#fff1a8",
                    )
                ),
                outline="",
                tags="dust",
            )

            speed = random.uniform(
                1.2,
                4.8,
            )

            dust_particles.append(
                {
                    "id": particle,
                    "x": x,
                    "y": y,
                    "vx": (
                        math.cos(angle)
                        * speed
                    ),
                    "vy": (
                        math.sin(angle)
                        * speed
                        - random.uniform(
                            0.3,
                            1.8,
                        )
                    ),
                    "size": size,
                }
            )

    def animate_dust(step=0):
        if step >= 42:
            window.destroy()
            return

        canvas.delete("coin")

        for particle in dust_particles:
            particle["x"] += (
                particle["vx"]
            )

            particle["y"] += (
                particle["vy"]
            )

            particle["vy"] += 0.11
            particle["vx"] *= 0.975
            particle["size"] *= 0.925

            if particle["size"] <= 0.2:
                canvas.delete(
                    particle["id"]
                )
                continue

            size = particle["size"]

            canvas.coords(
                particle["id"],
                particle["x"] - size,
                particle["y"] - size,
                particle["x"] + size,
                particle["y"] + size,
            )

        window.after(
            24,
            lambda: animate_dust(
                step + 1
            ),
        )

    def show_result():
        canvas.delete(
            "result"
        )

        canvas.create_text(
            center_x,
            238,
            text=result.upper(),
            fill="#fff1a8",
            font=(
                "Segoe UI",
                18,
                "bold",
            ),
            tags="result",
        )

        canvas.create_text(
            center_x,
            260,
            text="THE COIN HAS LANDED",
            fill="#687180",
            font=(
                "Segoe UI",
                6,
                "bold",
            ),
            tags="result",
        )

    def start_dust():
        canvas.delete(
            "result"
        )

        create_coin_particles()

        window.after(
            20,
            animate_dust,
        )

    def animate():
        nonlocal frame

        if frame >= total_frames:
            draw_coin(
                1.0,
                0,
                base_y,
            )

            show_result()

            if result_callback:
                result_callback(
                    result
                )

            window.after(
                1300,
                start_dust,
            )

            return

        progress = (
            frame
            / total_frames
        )

        rotation = (
            progress
            * math.pi
            * 18
        )

        scale_x = abs(
            math.cos(
                rotation
            )
        )

        ease = (
            1
            - (
                1
                - progress
            ) ** 3
        )

        current_scale = max(
            0.05,
            scale_x
            * (
                0.78
                + (
                    0.22
                    * ease
                )
            ),
        )

        bounce = (
            math.sin(
                progress
                * math.pi
            )
            * 18
        )

        coin_y = (
            base_y
            - bounce
        )

        draw_coin(
            current_scale,
            int(
                rotation
                / math.pi
            ) % 2,
            coin_y,
        )

        frame += 1

        delay = int(
            13
            + progress * 18
        )

        window.after(
            delay,
            animate,
        )

    animate()
    try:
        window.update_idletasks()
        window.deiconify()
        window.lift()
    except tk.TclError:
        try:
            window.destroy()
        except tk.TclError:
            pass
        return "Could not display the coin flip window."

    parent.wait_window(window)

    return f"The coin flip returned {result}."


_dice_last_time = 0.0


def roll_dice_animation(parent, result_callback=None):
    global _dice_last_time

    now = time.monotonic()

    if now - _dice_last_time < 10:
        remaining = max(
            1,
            math.ceil(
                10 - (
                    now - _dice_last_time
                )
            ),
        )

        try:
            parent.bell()
        except Exception:
            pass

        return (
            f"Dice roll is on cooldown. "
            f"Try again in {remaining} seconds."
        )

    _dice_last_time = now

    width = 430
    height = 285

    window = tk.Toplevel(parent)
    window.withdraw()
    window.overrideredirect(True)
    window.resizable(False, False)
    window.attributes("-topmost", True)
    window.configure(
        bg="#080a0f"
    )

    try:
        window.attributes(
            "-alpha",
            0.98,
        )
    except Exception:
        pass

    window.update_idletasks()

    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()

    screen_width = parent.winfo_screenwidth()
    screen_height = parent.winfo_screenheight()

    gap = 14

    right_x = (
        parent_x
        + parent_width
        + gap
    )

    left_x = (
        parent_x
        - width
        - gap
    )

    if right_x + width <= screen_width - 8:
        x = right_x
    elif left_x >= 8:
        x = left_x
    else:
        x = max(
            8,
            min(
                parent_x
                + (
                    parent_width
                    - width
                )
                // 2,
                screen_width
                - width
                - 8,
            ),
        )

    y = (
        parent_y
        + (
            parent_height
            - height
        )
        // 2
    )

    y = max(
        8,
        min(
            y,
            screen_height
            - height
            - 8,
        ),
    )

    window.geometry(
        f"{width}x{height}+{x}+{y}"
    )

    drag_data = {
        "x": 0,
        "y": 0,
    }

    def start_drag(event):
        drag_data["x"] = event.x_root
        drag_data["y"] = event.y_root

    def drag_window(event):
        delta_x = (
            event.x_root
            - drag_data["x"]
        )

        delta_y = (
            event.y_root
            - drag_data["y"]
        )

        current_x = window.winfo_x()
        current_y = window.winfo_y()

        new_x = current_x + delta_x
        new_y = current_y + delta_y

        new_x = max(
            4,
            min(
                new_x,
                screen_width
                - width
                - 4,
            ),
        )

        new_y = max(
            4,
            min(
                new_y,
                screen_height
                - height
                - 4,
            ),
        )

        window.geometry(
            f"{width}x{height}+{new_x}+{new_y}"
        )

        drag_data["x"] = event.x_root
        drag_data["y"] = event.y_root

    canvas = tk.Canvas(
        window,
        width=width,
        height=height,
        bg="#080a0f",
        highlightthickness=0,
        bd=0,
    )

    canvas.pack(
        fill="both",
        expand=True,
    )

    canvas.bind(
        "<ButtonPress-1>",
        start_drag,
    )

    canvas.bind(
        "<B1-Motion>",
        drag_window,
    )

    canvas.create_rectangle(
        1,
        1,
        width - 1,
        height - 1,
        fill="#0d1017",
        outline="#252b36",
        width=1,
    )

    canvas.create_rectangle(
        10,
        10,
        width - 10,
        height - 10,
        fill="#0a0d13",
        outline="#171c25",
        width=1,
    )

    canvas.create_line(
        22,
        22,
        width - 22,
        22,
        fill="#252b36",
        width=1,
    )

    canvas.create_text(
        28,
        66,
        text="Zanel",
        anchor="w",
        fill="#3ecf79",
        font=(
            "Segoe UI",
            8,
            "bold",
        ),
    )

    canvas.create_text(
        28,
        91,
        text="DICE ROLL",
        anchor="w",
        fill="#ffffff",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    )

    canvas.create_line(
        28,
        112,
        28,
        166,
        fill="#3ecf79",
        width=2,
    )

    canvas.create_text(
        28,
        190,
        text="RANDOM",
        anchor="w",
        fill="#687180",
        font=(
            "Segoe UI",
            6,
            "bold",
        ),
    )

    canvas.create_text(
        28,
        205,
        text="ROLL THE DICE",
        anchor="w",
        fill="#3f4652",
        font=(
            "Segoe UI",
            6,
            "bold",
        ),
    )

    result = random.randint(
        1,
        6,
    )

    center_x = 280
    center_y = 137

    frame = 0
    total_frames = 105

    fragments = []
    sparks = []

    def rotate_point(px, py, pz, angle_y, angle_x):
        cos_y = math.cos(
            angle_y
        )

        sin_y = math.sin(
            angle_y
        )

        x1 = (
            px * cos_y
            + pz * sin_y
        )

        z1 = (
            -px * sin_y
            + pz * cos_y
        )

        cos_x = math.cos(
            angle_x
        )

        sin_x = math.sin(
            angle_x
        )

        y1 = (
            py * cos_x
            - z1 * sin_x
        )

        z2 = (
            py * sin_x
            + z1 * cos_x
        )

        return x1, y1, z2

    def cube_point(
        px,
        py,
        pz,
        angle_y,
        angle_x,
        scale,
    ):
        x1, y1, z2 = rotate_point(
            px,
            py,
            pz,
            angle_y,
            angle_x,
        )

        perspective = (
            1
            + (
                z2
                / 520
            )
        )

        return (
            center_x
            + (
                x1
                * scale
                * perspective
            ),
            current_center_y
            + (
                y1
                * scale
                * perspective
            ),
            z2,
        )

    def draw_face(points):
        projected = []

        for point in points:
            projected.append(
                cube_point(
                    point[0],
                    point[1],
                    point[2],
                    current_angle_y,
                    current_angle_x,
                    current_scale,
                )
            )

        edge_a = tuple(
            points[1][index] - points[0][index]
            for index in range(3)
        )
        edge_b = tuple(
            points[3][index] - points[0][index]
            for index in range(3)
        )
        normal = (
            edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
            edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
            edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
        )
        rotated_normal = rotate_point(
            normal[0],
            normal[1],
            normal[2],
            current_angle_y,
            current_angle_x,
        )

        if rotated_normal[2] <= 0:
            return None

        depth = sum(
            point[2]
            for point in projected
        ) / len(
            projected
        )

        normal_length = math.sqrt(
            sum(component * component for component in rotated_normal)
        )
        light = (-0.35, -0.45, 0.82)
        brightness = 0.52 + 0.48 * max(
            0,
            sum(
                rotated_normal[index] * light[index]
                for index in range(3)
            ) / normal_length,
        )
        color = tuple(
            min(255, int(channel * brightness))
            for channel in (238, 242, 248)
        )
        fill = "#{:02x}{:02x}{:02x}".format(*color)

        return depth, projected, fill

    def draw_pip(
        number,
        face_points,
    ):
        positions = {
            1: [
                (0, 0),
            ],
            2: [
                (-0.36, -0.36),
                (0.36, 0.36),
            ],
            3: [
                (-0.36, -0.36),
                (0, 0),
                (0.36, 0.36),
            ],
            4: [
                (-0.36, -0.36),
                (0.36, -0.36),
                (-0.36, 0.36),
                (0.36, 0.36),
            ],
            5: [
                (-0.36, -0.36),
                (0.36, -0.36),
                (0, 0),
                (-0.36, 0.36),
                (0.36, 0.36),
            ],
            6: [
                (-0.36, -0.4),
                (-0.36, 0),
                (-0.36, 0.4),
                (0.36, -0.4),
                (0.36, 0),
                (0.36, 0.4),
            ],
        }

        p0, p1, _, p3 = face_points
        face_center = tuple(
            sum(point[index] for point in face_points) / 4
            for index in range(3)
        )
        axis_u = tuple(
            (p1[index] - p0[index]) / 2
            for index in range(3)
        )
        axis_v = tuple(
            (p3[index] - p0[index]) / 2
            for index in range(3)
        )

        for px, py in positions[number]:
            pip_center = tuple(
                face_center[index]
                + axis_u[index] * px * 0.78
                + axis_v[index] * py * 0.78
                for index in range(3)
            )
            coords = []

            for point_index in range(12):
                angle = point_index * math.tau / 12
                point = tuple(
                    pip_center[index]
                    + axis_u[index] * math.cos(angle) * 0.085
                    + axis_v[index] * math.sin(angle) * 0.085
                    for index in range(3)
                )
                projected = cube_point(
                    point[0],
                    point[1],
                    point[2],
                    current_angle_y,
                    current_angle_x,
                    current_scale,
                )
                coords.extend(projected[:2])

            canvas.create_polygon(
                *coords,
                fill="#10141b",
                outline="#080a0f",
                width=1,
                tags="dice_pip",
            )

    def draw_dice():
        canvas.delete(
            "dice"
        )

        canvas.delete(
            "dice_pip"
        )

        canvas.delete(
            "shadow"
        )

        size = 70
        shadow_width = 48 * current_scale
        lift = max(0, center_y - current_center_y)
        shadow_height = max(3, 8 * current_scale - lift * 0.08)
        shadow_y = center_y + 73 * current_scale

        canvas.create_oval(
            center_x - shadow_width,
            shadow_y - shadow_height,
            center_x + shadow_width,
            shadow_y + shadow_height,
            fill="#171c24",
            outline="",
            tags="shadow",
        )

        vertices = {
            "000": (
                -size,
                -size,
                -size,
            ),
            "001": (
                -size,
                -size,
                size,
            ),
            "010": (
                -size,
                size,
                -size,
            ),
            "011": (
                -size,
                size,
                size,
            ),
            "100": (
                size,
                -size,
                -size,
            ),
            "101": (
                size,
                -size,
                size,
            ),
            "110": (
                size,
                size,
                -size,
            ),
            "111": (
                size,
                size,
                size,
            ),
        }

        faces = [
            (
                [
                    vertices["000"],
                    vertices["001"],
                    vertices["011"],
                    vertices["010"],
                ],
                2,
            ),
            (
                [
                    vertices["100"],
                    vertices["110"],
                    vertices["111"],
                    vertices["101"],
                ],
                5,
            ),
            (
                [
                    vertices["000"],
                    vertices["100"],
                    vertices["101"],
                    vertices["001"],
                ],
                3,
            ),
            (
                [
                    vertices["010"],
                    vertices["011"],
                    vertices["111"],
                    vertices["110"],
                ],
                4,
            ),
            (
                [
                    vertices["001"],
                    vertices["101"],
                    vertices["111"],
                    vertices["011"],
                ],
                1,
            ),
            (
                [
                    vertices["000"],
                    vertices["010"],
                    vertices["110"],
                    vertices["100"],
                ],
                6,
            ),
        ]

        rendered = []

        for face, number in faces:
            projection = draw_face(face)

            if projection is not None:
                depth, points, fill = projection
                rendered.append((depth, face, number, points, fill))

        rendered.sort(
            key=lambda item: item[0]
        )

        for _, face, number, points, fill in rendered:
            coords = [
                coordinate
                for point in points
                for coordinate in point[:2]
            ]
            canvas.create_polygon(
                *coords,
                fill=fill,
                outline="#69727f",
                width=2,
                tags="dice",
            )
            draw_pip(
                number,
                face,
            )

    def create_fragments():
        fragments.clear()
        sparks.clear()

        for _ in range(150):
            angle = random.uniform(
                0,
                math.pi * 2,
            )

            distance = random.uniform(
                15,
                72,
            )

            x = (
                center_x
                + math.cos(angle)
                * distance
            )

            y = (
                center_y
                + math.sin(angle)
                * distance
            )

            size = random.uniform(
                1.5,
                5.0,
            )

            particle = canvas.create_polygon(
                x,
                y,
                x + size,
                y - size * 0.4,
                x + size * 0.4,
                y + size,
                fill=random.choice(
                    (
                        "#ffffff",
                        "#dce2e8",
                        "#3ecf79",
                        "#79e3a4",
                        "#aeb4bd",
                    )
                ),
                outline="",
                tags="fragment",
            )

            speed = random.uniform(
                1.5,
                5.5,
            )

            fragments.append(
                {
                    "id": particle,
                    "x": x,
                    "y": y,
                    "vx": (
                        math.cos(angle)
                        * speed
                    ),
                    "vy": (
                        math.sin(angle)
                        * speed
                        - random.uniform(
                            1.0,
                            3.0,
                        )
                    ),
                    "size": size,
                    "rotation": random.uniform(
                        0,
                        math.pi * 2,
                    ),
                    "spin": random.uniform(
                        -0.25,
                        0.25,
                    ),
                }
            )

        for _ in range(80):
            angle = random.uniform(
                0,
                math.pi * 2,
            )

            distance = random.uniform(
                10,
                55,
            )

            x = (
                center_x
                + math.cos(angle)
                * distance
            )

            y = (
                center_y
                + math.sin(angle)
                * distance
            )

            size = random.uniform(
                1,
                2.5,
            )

            spark = canvas.create_oval(
                x - size,
                y - size,
                x + size,
                y + size,
                fill=random.choice(
                    (
                        "#3ecf79",
                        "#79e3a4",
                        "#ffffff",
                    )
                ),
                outline="",
                tags="spark",
            )

            sparks.append(
                {
                    "id": spark,
                    "x": x,
                    "y": y,
                    "vx": random.uniform(
                        -3.5,
                        3.5,
                    ),
                    "vy": random.uniform(
                        -4.5,
                        1.5,
                    ),
                    "life": random.randint(
                        20,
                        50,
                    ),
                }
            )

    def animate_fragments(
        step=0,
    ):
        if step >= 55:
            canvas.delete(
                "fragment"
            )

            canvas.delete(
                "spark"
            )

            window.destroy()
            return

        canvas.delete(
            "result"
        )

        for particle in fragments:
            particle["x"] += (
                particle["vx"]
            )

            particle["y"] += (
                particle["vy"]
            )

            particle["vy"] += 0.12

            particle["vx"] *= 0.975

            particle["rotation"] += (
                particle["spin"]
            )

            particle["size"] *= 0.94

            size = particle["size"]

            if size <= 0.25:
                canvas.delete(
                    particle["id"]
                )
                continue

            x = particle["x"]
            y = particle["y"]

            canvas.coords(
                particle["id"],
                x,
                y,
                x + size,
                y - size * 0.4,
                x + size * 0.4,
                y + size,
            )

        for spark in sparks:
            spark["x"] += (
                spark["vx"]
            )

            spark["y"] += (
                spark["vy"]
            )

            spark["vy"] += 0.08

            spark["life"] -= 1

            if spark["life"] <= 0:
                canvas.delete(
                    spark["id"]
                )
                continue

            size = max(
                0.3,
                spark["life"]
                / 12,
            )

            canvas.coords(
                spark["id"],
                spark["x"] - size,
                spark["y"] - size,
                spark["x"] + size,
                spark["y"] + size,
            )

        window.after(
            24,
            lambda: animate_fragments(
                step + 1
            ),
        )

    def show_result():
        canvas.delete(
            "result"
        )

        canvas.create_text(
            center_x,
            235,
            text=str(result),
            fill="#ffffff",
            font=(
                "Segoe UI",
                25,
                "bold",
            ),
            tags="result",
        )

        canvas.create_text(
            center_x,
            263,
            text="THE DICE HAS LANDED",
            fill="#687180",
            font=(
                "Segoe UI",
                6,
                "bold",
            ),
            tags="result",
        )

    current_angle_y = 0.0
    current_angle_x = 0.0
    current_scale = 0.72
    current_center_y = center_y
    final_angles = {
        1: (0.14, -0.12),
        2: (math.pi / 2 - 0.14, 0.12),
        3: (-0.12, -math.pi / 2 + 0.14),
        4: (0.12, math.pi / 2 - 0.14),
        5: (-math.pi / 2 + 0.14, -0.12),
        6: (math.pi - 0.14, 0.12),
    }

    def animate():
        nonlocal frame
        nonlocal current_angle_y
        nonlocal current_angle_x
        nonlocal current_scale
        nonlocal current_center_y

        if frame >= total_frames:
            current_angle_y, current_angle_x = final_angles[result]
            current_scale = 0.72
            current_center_y = center_y

            draw_dice()

            show_result()

            if result_callback:
                result_callback(
                    result
                )

            window.after(
                1300,
                start_disintegration,
            )

            return

        progress = (
            frame
            / total_frames
        )

        ease = (
            1
            - (
                1
                - progress
            ) ** 3
        )

        target_angle_y, target_angle_x = final_angles[result]
        current_angle_y = ease * (
            target_angle_y + math.tau * 4
        )
        current_angle_x = ease * (
            target_angle_x + math.tau * 3
        )

        bounce = (
            math.sin(
                progress
                * math.tau
                * 2
            )
            * 24
            * (
                1
                - progress
            )
        )
        current_center_y = center_y - bounce

        current_scale = (
            0.56
            + (
                0.20
                * ease
            )
        )

        draw_dice()

        frame += 1

        delay = int(
            14
            + progress
            * 22
        )

        window.after(
            delay,
            animate,
        )

    def start_disintegration():
        canvas.delete(
            "result"
        )

        canvas.delete(
            "shadow"
        )

        canvas.delete(
            "dice"
        )

        canvas.delete(
            "dice_pip"
        )

        create_fragments()

        window.after(
            20,
            animate_fragments,
        )

    animate()
    try:
        window.update_idletasks()
        window.deiconify()
        window.lift()
    except tk.TclError:
        try:
            window.destroy()
        except tk.TclError:
            pass
        return "Could not display the dice roll window."

    parent.wait_window(window)

    return f"The dice roll returned a {result}."


_confetti_last_time = 0.0


_confetti_window = None


_confetti_popup = None


_confetti_lock = threading.Lock()


def confetti_animation(parent):
    global _confetti_last_time
    global _confetti_window
    global _confetti_popup

    now = time.monotonic()

    with _confetti_lock:
        remaining_time = 10.0 - (
            now - _confetti_last_time
        )

        if remaining_time > 0:
            remaining = max(
                1,
                math.ceil(
                    remaining_time
                )
            )

            try:
                parent.after(
                    0,
                    lambda: show_confetti_cooldown(
                        parent,
                        remaining
                    )
                )
            except tk.TclError:
                pass

            return (
                f"Confetti is cooling down. "
                f"{remaining} seconds remaining."
            )

        _confetti_last_time = now

    try:
        parent.after(
            0,
            lambda: start_confetti_animation(
                parent
            )
        )

        return (
            "Rainbow confetti celebration "
            "started across Zanel."
        )

    except tk.TclError:
        with _confetti_lock:
            _confetti_last_time = 0.0

        return "Could not launch the confetti."


def get_confetti_app(parent):
    try:
        if hasattr(parent, "compact_window"):
            return parent

        owner = parent.master

        if owner is not None and hasattr(
            owner,
            "compact_window"
        ):
            return owner

    except Exception:
        pass

    return None


def get_confetti_target(parent):
    app = get_confetti_app(parent)

    if app is not None:
        try:
            compact = getattr(
                app,
                "compact_window",
                None
            )

            if compact is not None:
                try:
                    if (
                        compact.winfo_exists()
                        and compact.state()
                        not in (
                            "withdrawn",
                            "iconic"
                        )
                        and compact.winfo_width() > 1
                        and compact.winfo_height() > 1
                    ):
                        return compact
                except tk.TclError:
                    pass

        except Exception:
            pass

    try:
        if (
            parent.winfo_exists()
            and parent.state()
            not in (
                "withdrawn",
                "iconic"
            )
            and parent.winfo_width() > 1
            and parent.winfo_height() > 1
        ):
            return parent
    except tk.TclError:
        pass

    return None


def show_confetti_cooldown(
    parent,
    remaining
):
    global _confetti_popup

    try:
        if _confetti_popup is not None:
            try:
                if _confetti_popup.winfo_exists():
                    return
            except tk.TclError:
                _confetti_popup = None

        target = get_confetti_target(
            parent
        )

        popup_width = 350
        popup_height = 175

        if target is not None:
            target.update_idletasks()

            target_width = target.winfo_width()
            target_height = target.winfo_height()

            if (
                target_width > 1
                and target_height > 1
            ):
                popup_x = (
                    target.winfo_rootx()
                    + (
                        target_width
                        - popup_width
                    ) // 2
                )

                popup_y = (
                    target.winfo_rooty()
                    + (
                        target_height
                        - popup_height
                    ) // 2
                )
            else:
                target = None

        if target is None:
            screen_width = (
                parent.winfo_screenwidth()
            )

            screen_height = (
                parent.winfo_screenheight()
            )

            popup_x = (
                screen_width
                - popup_width
            ) // 2

            popup_y = (
                screen_height
                - popup_height
            ) // 2

        popup = tk.Toplevel()
        _confetti_popup = popup

        popup.overrideredirect(True)

        popup.geometry(
            f"{popup_width}x{popup_height}+"
            f"{popup_x}+{popup_y}"
        )

        popup.configure(
            bg="#5CFF9D"
        )

        try:
            popup.attributes(
                "-topmost",
                True
            )
        except tk.TclError:
            pass

        outer = tk.Frame(
            popup,
            bg="#5CFF9D"
        )

        outer.pack(
            fill="both",
            expand=True
        )

        inner = tk.Frame(
            outer,
            bg="#0D1713"
        )

        inner.pack(
            fill="both",
            expand=True,
            padx=2,
            pady=2
        )

        title = tk.Label(
            inner,
            text="✦ CONFETTI COOLDOWN ✦",
            fg="#5CFF9D",
            bg="#0D1713",
            font=(
                "Segoe UI",
                11,
                "bold"
            )
        )

        title.pack(
            pady=(17, 3)
        )

        tk.Label(
            inner,
            text="The party is recharging...",
            fg="#E8F5ED",
            bg="#0D1713",
            font=(
                "Segoe UI",
                9
            )
        ).pack()

        countdown = tk.Label(
            inner,
            text=str(remaining),
            fg="#FFFFFF",
            bg="#0D1713",
            font=(
                "Segoe UI",
                30,
                "bold"
            )
        )

        countdown.pack(
            pady=(3, 0)
        )

        bar_background = tk.Frame(
            inner,
            bg="#202A25",
            height=5
        )

        bar_background.pack(
            fill="x",
            padx=28,
            pady=(3, 18)
        )

        bar = tk.Frame(
            bar_background,
            bg="#5CFF9D",
            height=5
        )

        bar.place(
            x=0,
            y=0,
            relheight=1.0,
            relwidth=max(
                0.0,
                min(
                    1.0,
                    remaining / 10
                )
            )
        )

        started = time.monotonic()

        def update_popup():
            global _confetti_popup

            try:
                if not popup.winfo_exists():
                    if _confetti_popup is popup:
                        _confetti_popup = None
                    return
            except tk.TclError:
                if _confetti_popup is popup:
                    _confetti_popup = None
                return

            left = (
                10.0
                - (
                    time.monotonic()
                    - _confetti_last_time
                )
            )

            if left <= 0:
                try:
                    popup.destroy()
                except tk.TclError:
                    pass

                if _confetti_popup is popup:
                    _confetti_popup = None

                return

            seconds = max(
                1,
                math.ceil(left)
            )

            countdown.configure(
                text=str(seconds)
            )

            progress = max(
                0.0,
                min(
                    1.0,
                    left / 10.0
                )
            )

            bar.place(
                x=0,
                y=0,
                relheight=1.0,
                relwidth=progress
            )

            pulse = (
                math.sin(
                    (
                        time.monotonic()
                        - started
                    ) * 5
                )
                + 1
            ) / 2

            title.configure(
                fg=(
                    "#FFFFFF"
                    if pulse > 0.5
                    else "#5CFF9D"
                )
            )

            try:
                popup.after(
                    50,
                    update_popup
                )
            except tk.TclError:
                if _confetti_popup is popup:
                    _confetti_popup = None

        update_popup()

    except Exception:
        try:
            if _confetti_popup is not None:
                _confetti_popup.destroy()
        except Exception:
            pass

        _confetti_popup = None


def start_confetti_animation(
    parent
):
    global _confetti_window
    global _confetti_last_time

    if _confetti_window is not None:
        try:
            if _confetti_window.winfo_exists():
                return
        except tk.TclError:
            _confetti_window = None

    try:
        target = get_confetti_target(
            parent
        )

        if target is None:
            with _confetti_lock:
                _confetti_last_time = 0.0

            return

        target.update_idletasks()

        x = target.winfo_rootx()
        y = target.winfo_rooty()
        width = target.winfo_width()
        height = target.winfo_height()

        if width <= 1:
            width = target.winfo_reqwidth()

        if height <= 1:
            height = target.winfo_reqheight()

        if width <= 1 or height <= 1:
            with _confetti_lock:
                _confetti_last_time = 0.0

            return

        overlay = tk.Toplevel()

        _confetti_window = overlay

        overlay.overrideredirect(
            True
        )

        overlay.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        transparent = "#010101"

        overlay.configure(
            bg=transparent
        )

        try:
            overlay.attributes(
                "-topmost",
                True
            )
        except tk.TclError:
            pass

        try:
            overlay.attributes(
                "-transparentcolor",
                transparent
            )
        except tk.TclError:
            try:
                overlay.destroy()
            except tk.TclError:
                pass

            _confetti_window = None

            with _confetti_lock:
                _confetti_last_time = 0.0

            return

        try:
            overlay.attributes(
                "-disabled",
                True
            )
        except tk.TclError:
            pass

        canvas = tk.Canvas(
            overlay,
            width=width,
            height=height,
            bg=transparent,
            bd=0,
            highlightthickness=0,
            relief="flat"
        )

        canvas.pack(
            fill="both",
            expand=True
        )

        rainbow = (
            "#FF1744",
            "#FF4081",
            "#FF6D00",
            "#FFD600",
            "#76FF03",
            "#00E676",
            "#00E5FF",
            "#2979FF",
            "#651FFF",
            "#D500F9",
            "#FFFFFF"
        )

        particles = []
        explosions = []
        trails = []
        sparkles = []
        rings = []

        def star_points(
            cx,
            cy,
            radius,
            rotation
        ):
            points = []

            for index in range(10):
                angle = (
                    rotation
                    + index
                    * math.pi
                    / 5
                )

                current_radius = (
                    radius
                    if index % 2 == 0
                    else radius * 0.38
                )

                points.extend(
                    (
                        cx
                        + math.cos(angle)
                        * current_radius,
                        cy
                        + math.sin(angle)
                        * current_radius
                    )
                )

            return points

        def heart_points(
            cx,
            cy,
            size,
            rotation
        ):
            points = []

            for index in range(24):
                angle = (
                    math.pi * 2
                    * index
                    / 24
                )

                hx = (
                    16
                    * math.sin(angle) ** 3
                )

                hy = -(
                    13
                    * math.cos(angle)
                    - 5
                    * math.cos(
                        2 * angle
                    )
                    - 2
                    * math.cos(
                        3 * angle
                    )
                    - math.cos(
                        4 * angle
                    )
                )

                px = (
                    hx
                    * size
                    / 16
                )

                py = (
                    hy
                    * size
                    / 16
                )

                cos_r = math.cos(
                    rotation
                )

                sin_r = math.sin(
                    rotation
                )

                points.extend(
                    (
                        cx
                        + px * cos_r
                        - py * sin_r,
                        cy
                        + px * sin_r
                        + py * cos_r
                    )
                )

            return points

        def create_particle(
            px,
            py,
            vx,
            vy,
            size,
            color,
            shape,
            delay=0.0,
            gravity=None
        ):
            rotation = random.uniform(
                0,
                math.pi * 2
            )

            if gravity is None:
                gravity = random.uniform(
                    0.09,
                    0.22
                )

            if shape == "circle":
                item = canvas.create_oval(
                    px - size,
                    py - size,
                    px + size,
                    py + size,
                    fill=color,
                    outline=""
                )

            elif shape == "star":
                item = canvas.create_polygon(
                    *star_points(
                        px,
                        py,
                        size,
                        rotation
                    ),
                    fill=color,
                    outline=""
                )

            elif shape == "heart":
                item = canvas.create_polygon(
                    *heart_points(
                        px,
                        py,
                        size,
                        rotation
                    ),
                    fill=color,
                    outline=""
                )

            elif shape == "diamond":
                item = canvas.create_polygon(
                    px,
                    py - size,
                    px + size * 0.7,
                    py,
                    px,
                    py + size,
                    px - size * 0.7,
                    py,
                    fill=color,
                    outline=""
                )

            elif shape == "ribbon":
                item = canvas.create_line(
                    px - size * 2,
                    py,
                    px - size * 0.8,
                    py - size,
                    px + size * 0.4,
                    py + size,
                    px + size * 2,
                    py - size * 0.2,
                    fill=color,
                    width=max(
                        2,
                        int(size * 0.65)
                    ),
                    smooth=True
                )

            elif shape == "spark":
                item = canvas.create_line(
                    px - size,
                    py,
                    px + size,
                    py,
                    fill=color,
                    width=max(
                        1,
                        int(size * 0.55)
                    )
                )

            else:
                item = canvas.create_rectangle(
                    px - size,
                    py - size * 0.5,
                    px + size,
                    py + size * 0.5,
                    fill=color,
                    outline=""
                )

            particles.append(
                {
                    "id": item,
                    "x": px,
                    "y": py,
                    "vx": vx,
                    "vy": vy,
                    "size": size,
                    "shape": shape,
                    "rotation": rotation,
                    "spin": random.uniform(
                        -0.55,
                        0.55
                    ),
                    "gravity": gravity,
                    "drag": random.uniform(
                        0.982,
                        0.998
                    ),
                    "delay": delay,
                    "age": 0.0,
                    "life": random.uniform(
                        2.0,
                        4.4
                    )
                }
            )

        for direction in (
            1,
            -1
        ):
            start_x = (
                -15
                if direction == 1
                else width + 15
            )

            for _ in range(140):
                py = random.uniform(
                    height * 0.08,
                    height * 0.92
                )

                angle = random.uniform(
                    -1.05,
                    1.05
                )

                speed = random.uniform(
                    280,
                    760
                )

                create_particle(
                    start_x
                    + random.uniform(
                        -15,
                        15
                    ),
                    py,
                    math.cos(angle)
                    * speed
                    * direction,
                    math.sin(angle)
                    * speed,
                    random.uniform(
                        3,
                        8
                    ),
                    random.choice(
                        rainbow
                    ),
                    random.choice(
                        (
                            "rectangle",
                            "rectangle",
                            "diamond",
                            "circle",
                            "star",
                            "heart",
                            "ribbon",
                            "spark"
                        )
                    ),
                    random.uniform(
                        0,
                        0.8
                    )
                )

        for _ in range(130):
            angle = random.uniform(
                0,
                math.pi * 2
            )

            speed = random.uniform(
                220,
                850
            )

            create_particle(
                width / 2
                + random.uniform(
                    -25,
                    25
                ),
                height / 2
                + random.uniform(
                    -25,
                    25
                ),
                math.cos(angle)
                * speed,
                math.sin(angle)
                * speed,
                random.uniform(
                    3,
                    8
                ),
                random.choice(
                    rainbow
                ),
                random.choice(
                    (
                        "star",
                        "diamond",
                        "circle",
                        "heart",
                        "ribbon",
                        "spark"
                    )
                ),
                random.uniform(
                    0.1,
                    0.85
                )
            )

        for _ in range(75):
            create_particle(
                random.uniform(
                    width * 0.05,
                    width * 0.95
                ),
                random.uniform(
                    -40,
                    height * 0.1
                ),
                random.uniform(
                    -100,
                    100
                ),
                random.uniform(
                    180,
                    500
                ),
                random.uniform(
                    3,
                    7
                ),
                random.choice(
                    rainbow
                ),
                random.choice(
                    (
                        "rectangle",
                        "diamond",
                        "circle",
                        "star",
                        "ribbon"
                    )
                ),
                random.uniform(
                    0.2,
                    1.4
                )
            )

        explosion_points = (
            (
                width * 0.08,
                height * 0.30
            ),
            (
                width * 0.92,
                height * 0.30
            ),
            (
                width * 0.16,
                height * 0.72
            ),
            (
                width * 0.84,
                height * 0.72
            ),
            (
                width * 0.50,
                height * 0.50
            )
        )

        for ex, ey in explosion_points:
            flash = canvas.create_oval(
                ex - 4,
                ey - 4,
                ex + 4,
                ey + 4,
                fill="#FFFFFF",
                outline=""
            )

            explosions.append(
                {
                    "id": flash,
                    "x": ex,
                    "y": ey,
                    "age": 0.0,
                    "radius": 4.0,
                    "max": random.uniform(
                        75,
                        155
                    )
                }
            )

            ring = canvas.create_oval(
                ex,
                ey,
                ex,
                ey,
                outline=random.choice(
                    rainbow
                ),
                width=3
            )

            rings.append(
                {
                    "id": ring,
                    "x": ex,
                    "y": ey,
                    "radius": 2.0,
                    "speed": random.uniform(
                        90,
                        190
                    ),
                    "max": random.uniform(
                        90,
                        170
                    )
                }
            )

            for ray in range(18):
                angle = (
                    math.pi * 2
                    * ray
                    / 18
                )

                length = random.uniform(
                    20,
                    70
                )

                line = canvas.create_line(
                    ex,
                    ey,
                    ex
                    + math.cos(angle)
                    * length,
                    ey
                    + math.sin(angle)
                    * length,
                    fill=random.choice(
                        rainbow
                    ),
                    width=random.randint(
                        1,
                        3
                    )
                )

                trails.append(
                    {
                        "id": line,
                        "x": ex,
                        "y": ey,
                        "angle": angle,
                        "length": length,
                        "speed": random.uniform(
                            80,
                            180
                        ),
                        "age": 0.0,
                        "life": random.uniform(
                            0.45,
                            0.9
                        )
                    }
                )

        for _ in range(55):
            sx = random.uniform(
                width * 0.04,
                width * 0.96
            )

            sy = random.uniform(
                height * 0.04,
                height * 0.96
            )

            item = canvas.create_line(
                sx - 7,
                sy,
                sx + 7,
                sy,
                fill=random.choice(
                    rainbow
                ),
                width=2
            )

            sparkles.append(
                {
                    "id": item,
                    "x": sx,
                    "y": sy,
                    "age": random.uniform(
                        0,
                        1
                    ),
                    "life": random.uniform(
                        0.7,
                        2.5
                    ),
                    "phase": random.uniform(
                        0,
                        math.pi * 2
                    )
                }
            )

        start_time = time.monotonic()
        last_time = start_time
        duration = 4.8
        finished = False

        def cleanup():
            global _confetti_window

            nonlocal finished

            if finished:
                return

            finished = True

            try:
                if overlay.winfo_exists():
                    overlay.destroy()
            except Exception:
                pass

            if _confetti_window is overlay:
                _confetti_window = None

        def update_particle(
            particle,
            dt,
            elapsed
        ):
            if elapsed < particle["delay"]:
                return

            particle["age"] += dt

            particle["x"] += (
                particle["vx"]
                * dt
            )

            particle["y"] += (
                particle["vy"]
                * dt
            )

            particle["vy"] += (
                particle["gravity"]
                * 60
                * dt
            )

            particle["vx"] *= (
                particle["drag"]
                ** (
                    dt * 60
                )
            )

            particle["rotation"] += (
                particle["spin"]
                * dt
                * 60
            )

            if (
                particle["age"]
                >= particle["life"]
            ):
                try:
                    canvas.delete(
                        particle["id"]
                    )
                except tk.TclError:
                    pass

                return

            px = particle["x"]
            py = particle["y"]
            size = particle["size"]
            rotation = particle["rotation"]
            shape = particle["shape"]

            if shape == "circle":
                scale = max(
                    0.08,
                    abs(
                        math.cos(
                            rotation
                        )
                    )
                )

                canvas.coords(
                    particle["id"],
                    px
                    - size * scale,
                    py - size,
                    px
                    + size * scale,
                    py + size
                )

            elif shape == "star":
                canvas.coords(
                    particle["id"],
                    *star_points(
                        px,
                        py,
                        size,
                        rotation
                    )
                )

            elif shape == "heart":
                canvas.coords(
                    particle["id"],
                    *heart_points(
                        px,
                        py,
                        size,
                        rotation
                    )
                )

            elif shape == "diamond":
                canvas.coords(
                    particle["id"],
                    px,
                    py - size,
                    px + size * 0.7,
                    py,
                    px,
                    py + size,
                    px - size * 0.7,
                    py
                )

            elif shape == "ribbon":
                wave = math.sin(
                    rotation * 2
                )

                canvas.coords(
                    particle["id"],
                    px - size * 2,
                    py,
                    px - size * 0.8,
                    py - size,
                    px + size * 0.4,
                    py
                    + size
                    * (
                        1
                        + wave * 0.3
                    ),
                    px + size * 2,
                    py - size * 0.2
                )

            elif shape == "spark":
                length = (
                    size
                    * (
                        0.7
                        + abs(
                            math.sin(
                                rotation
                            )
                        )
                    )
                )

                canvas.coords(
                    particle["id"],
                    px
                    - math.cos(
                        rotation
                    )
                    * length,
                    py
                    - math.sin(
                        rotation
                    )
                    * length,
                    px
                    + math.cos(
                        rotation
                    )
                    * length,
                    py
                    + math.sin(
                        rotation
                    )
                    * length
                )

            else:
                cos_r = math.cos(
                    rotation
                )

                sin_r = math.sin(
                    rotation
                )

                points = []

                for lx, ly in (
                    (
                        -size,
                        -size * 0.5
                    ),
                    (
                        size,
                        -size * 0.5
                    ),
                    (
                        size,
                        size * 0.5
                    ),
                    (
                        -size,
                        size * 0.5
                    )
                ):
                    points.extend(
                        (
                            px
                            + lx * cos_r
                            - ly * sin_r,
                            py
                            + lx * sin_r
                            + ly * cos_r
                        )
                    )

                canvas.coords(
                    particle["id"],
                    *points
                )

        def animate():
            nonlocal last_time

            if finished:
                return

            current_time = time.monotonic()

            elapsed = (
                current_time
                - start_time
            )

            dt = min(
                0.035,
                max(
                    0.001,
                    current_time
                    - last_time
                )
            )

            last_time = current_time

            if elapsed >= duration:
                cleanup()
                return

            try:
                if not overlay.winfo_exists():
                    cleanup()
                    return
            except tk.TclError:
                cleanup()
                return

            try:
                target = get_confetti_target(
                    parent
                )

                if target is not None:
                    target.update_idletasks()

                    state = target.state()

                    if state in (
                        "iconic",
                        "withdrawn"
                    ):
                        try:
                            overlay.withdraw()
                        except tk.TclError:
                            cleanup()
                            return
                    else:
                        new_x = target.winfo_rootx()
                        new_y = target.winfo_rooty()
                        new_width = target.winfo_width()
                        new_height = target.winfo_height()

                        if (
                            new_width > 1
                            and new_height > 1
                        ):
                            try:
                                if (
                                    overlay.state()
                                    == "withdrawn"
                                ):
                                    overlay.deiconify()
                            except tk.TclError:
                                cleanup()
                                return

                            overlay.geometry(
                                f"{new_width}x{new_height}+"
                                f"{new_x}+{new_y}"
                            )
                else:
                    try:
                        overlay.withdraw()
                    except tk.TclError:
                        cleanup()
                        return

            except Exception:
                try:
                    overlay.withdraw()
                except tk.TclError:
                    cleanup()
                    return

            for particle in particles:
                try:
                    update_particle(
                        particle,
                        dt,
                        elapsed
                    )
                except tk.TclError:
                    pass

            for explosion in explosions:
                explosion["age"] += dt

                progress = min(
                    1.0,
                    explosion["age"]
                    / 0.8
                )

                radius = (
                    explosion["radius"]
                    + (
                        explosion["max"]
                        * progress
                    )
                )

                try:
                    canvas.coords(
                        explosion["id"],
                        explosion["x"]
                        - radius,
                        explosion["y"]
                        - radius,
                        explosion["x"]
                        + radius,
                        explosion["y"]
                        + radius
                    )
                except tk.TclError:
                    pass

                if progress >= 1.0:
                    try:
                        canvas.delete(
                            explosion["id"]
                        )
                    except tk.TclError:
                        pass

            for ring in rings:
                ring["radius"] += (
                    ring["speed"]
                    * dt
                )

                if (
                    ring["radius"]
                    >= ring["max"]
                ):
                    try:
                        canvas.delete(
                            ring["id"]
                        )
                    except tk.TclError:
                        pass

                    continue

                radius = ring["radius"]

                try:
                    canvas.coords(
                        ring["id"],
                        ring["x"]
                        - radius,
                        ring["y"]
                        - radius,
                        ring["x"]
                        + radius,
                        ring["y"]
                        + radius
                    )

                    canvas.itemconfigure(
                        ring["id"],
                        width=max(
                            1,
                            int(
                                3
                                * (
                                    1
                                    - (
                                        radius
                                        / ring["max"]
                                    )
                                )
                            )
                        )
                    )
                except tk.TclError:
                    pass

            for trail in trails:
                trail["age"] += dt

                trail["length"] += (
                    trail["speed"]
                    * dt
                )

                try:
                    canvas.coords(
                        trail["id"],
                        trail["x"],
                        trail["y"],
                        trail["x"]
                        + math.cos(
                            trail["angle"]
                        )
                        * trail["length"],
                        trail["y"]
                        + math.sin(
                            trail["angle"]
                        )
                        * trail["length"]
                    )
                except tk.TclError:
                    pass

                if (
                    trail["age"]
                    >= trail["life"]
                ):
                    try:
                        canvas.delete(
                            trail["id"]
                        )
                    except tk.TclError:
                        pass

            for sparkle in sparkles:
                sparkle["age"] += dt

                pulse = (
                    math.sin(
                        sparkle["age"]
                        * 8
                        + sparkle["phase"]
                    )
                    + 1
                ) / 2

                size = (
                    1.5
                    + pulse * 7
                )

                try:
                    canvas.coords(
                        sparkle["id"],
                        sparkle["x"]
                        - size,
                        sparkle["y"],
                        sparkle["x"]
                        + size,
                        sparkle["y"]
                    )
                except tk.TclError:
                    pass

                if (
                    sparkle["age"]
                    >= sparkle["life"]
                ):
                    try:
                        canvas.delete(
                            sparkle["id"]
                        )
                    except tk.TclError:
                        pass

            if elapsed > 3.8:
                fade = max(
                    0.0,
                    1.0
                    - (
                        (
                            elapsed
                            - 3.8
                        )
                        / 1.0
                    )
                )

                try:
                    overlay.attributes(
                        "-alpha",
                        fade
                    )
                except tk.TclError:
                    pass

            try:
                if overlay.state() != "withdrawn":
                    overlay.lift()
            except tk.TclError:
                cleanup()
                return

            try:
                parent.after(
                    16,
                    animate
                )
            except tk.TclError:
                cleanup()

        try:
            overlay.update_idletasks()
            overlay.lift()
            animate()
        except Exception:
            cleanup()

            with _confetti_lock:
                _confetti_last_time = 0.0

    except Exception:
        try:
            if _confetti_window is not None:
                _confetti_window.destroy()
        except Exception:
            pass

        _confetti_window = None

        with _confetti_lock:
            _confetti_last_time = 0.0
