import os

async def execute_saga_job(payload: dict, conn) -> str:
    filename = payload.get("filename", "test.jpg")
    email = payload.get("email", "test@gmail.com")
    title = payload.get("title", "My Report")

    completed_steps = []

    try:
        print("Starting Saga for: " + title)

        print("Step 1: Resizing image...")
        from app.jobs.image import execute_image_job
        await execute_image_job({
            "filename": filename,
            "width": 300,
            "height": 300
        })
        completed_steps.append("resize_image")
        print("Step 1 done!")

        print("Step 2: Generating PDF...")
        from app.jobs.pdf import execute_pdf_job
        await execute_pdf_job({
            "title": title,
            "content": "Generated from image: " + filename
        })
        completed_steps.append("generate_pdf")
        print("Step 2 done!")

        print("Step 3: Sending email...")
        from app.jobs.email import execute_email_job
        await execute_email_job({
            "email": email,
            "subject": "Your report is ready!",
            "body": "Your PDF report " + title + " has been generated!"
        })
        completed_steps.append("send_email")
        print("Step 3 done!")

        print("Saga completed successfully!")
        return "Saga completed! Image resized, PDF generated, Email sent to " + email + "!"

    except Exception as e:
        print("Saga failed: " + str(e))
        print("Running compensating transactions...")

        if "generate_pdf" in completed_steps:
            print("Deleting PDF...")
            try:
                pdf_path = "/app/app/uploads/" + title.replace(" ", "_") + ".pdf"
                os.remove(pdf_path)
                print("PDF deleted!")
            except:
                print("PDF already gone!")

        if "resize_image" in completed_steps:
            print("Deleting resized image...")
            try:
                img_path = "/app/app/uploads/resized_" + filename
                os.remove(img_path)
                print("Resized image deleted!")
            except:
                print("Image already gone!")

        print("Compensation complete! System clean!")
        raise Exception("Saga failed and rolled back! Reason: " + str(e))