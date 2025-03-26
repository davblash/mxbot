import schedule
import time
from datetime import datetime, timedelta

def job():
    print(f"Job started at {datetime.now()}")
    # Simulate the job running for a certain period
    time.sleep(5)  # Replace 5 with the duration in seconds
    print(f"Job ended at {datetime.now()}")

def schedule_job(start_time, duration_minutes):
    def job_wrapper():
        job()
        # Stop the job after the specified duration
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        while datetime.now() < end_time:
            time.sleep(1)  # Keep the job running

    # Schedule the job every weekday at the specified start time
    schedule.every().monday.at(start_time).do(job_wrapper)
    schedule.every().tuesday.at(start_time).do(job_wrapper)
    schedule.every().wednesday.at(start_time).do(job_wrapper)
    schedule.every().thursday.at(start_time).do(job_wrapper)
    schedule.every().friday.at(start_time).do(job_wrapper)

# Configure the job
start_time = "00:35"  # Set the start time (24-hour format)
duration_minutes = 30  # Set the duration in minutes
schedule_job(start_time, duration_minutes)

print("Scheduler is running...")
while True:
    schedule.run_pending()
    time.sleep(1)