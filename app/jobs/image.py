from PIL import Image
from app.distributed.circuit_breaker import image_breaker

async def execute_image_job(payload: dict) -> str:
    filename = payload.get("filename", "test.jpg")
    width = payload.get("width", 800)
    height = payload.get("height", 600)

    if not image_breaker.can_call():
        raise Exception("Image service unavailable! Circuit breaker is OPEN!")

    try:
        input_path = "/app/app/uploads/" + filename
        output_path = "/app/app/uploads/resized_" + filename

        print("Resizing image: " + filename)

        img = Image.open(input_path)
        original_size = img.size
        img_resized = img.resize((width, height))
        img_resized.save(output_path)

        image_breaker.on_success()
        print("Image resized successfully!")
        return "Image " + filename + " resized to " + str(width) + "x" + str(height) + " successfully!"

    except Exception as e:
        image_breaker.on_failure()
        raise Exception("Image processing failed: " + str(e))