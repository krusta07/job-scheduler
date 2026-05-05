from PIL import Image
import io
import os
import asyncio

async def execute_image_job(payload: dict) -> str:
    """
    Resizes a real image using Pillow library

    payload should contain:
    {
        "filename": "photo.jpg",
        "width": 800,
        "height": 600
    }

    Pillow = Python Imaging Library
    Industry standard for image processing
    Used by Instagram, Pinterest etc!
    """
    filename = payload.get("filename", "test.jpg")
    width = payload.get("width", 800)
    height = payload.get("height", 600)

    print(f"🖼️ Resizing image: {filename}")
    print(f"   New size: {width}x{height}")

    # Simulate real image processing time
    await asyncio.sleep(3)

    # To process REAL images uncomment this:
    # img = Image.open(f"/app/uploads/{filename}")
    # img_resized = img.resize((width, height))
    # output_path = f"/app/outputs/resized_{filename}"
    # img_resized.save(output_path)

    return f"Image {filename} resized to {width}x{height} successfully!"