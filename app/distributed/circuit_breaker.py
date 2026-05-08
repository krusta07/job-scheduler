import time
import json
import os
import redis

def get_redis_client():
    return redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

class CircuitBreaker:
    def __init__(self, name, threshold=3, timeout=30):
        self.name = name
        self.threshold = threshold
        self.timeout = timeout
        self.key = "breaker:" + name

    def _get_state(self):
        try:
            r = get_redis_client()
            data = r.get(self.key)
            if data:
                return json.loads(data)
        except:
            pass
        return {
            "state": "CLOSED",
            "failure_count": 0,
            "last_failure_time": None
        }

    def _save_state(self, state):
        try:
            r = get_redis_client()
            r.set(self.key, json.dumps(state))
        except:
            pass

    def can_call(self):
        state = self._get_state()

        if state["state"] == "CLOSED":
            return True

        if state["state"] == "OPEN":
            if state["last_failure_time"]:
                seconds_passed = time.time() - state["last_failure_time"]
                if seconds_passed >= self.timeout:
                    print("Circuit " + self.name + " HALF OPEN, testing...")
                    state["state"] = "HALF_OPEN"
                    self._save_state(state)
                    return True
            print("Circuit " + self.name + " is OPEN! Blocking call!")
            return False

        if state["state"] == "HALF_OPEN":
            return True

        return True

    def on_success(self):
        print("Circuit " + self.name + " success! Closing circuit!")
        self._save_state({
            "state": "CLOSED",
            "failure_count": 0,
            "last_failure_time": None
        })

    def on_failure(self):
        state = self._get_state()
        state["failure_count"] += 1
        state["last_failure_time"] = time.time()
        print("Circuit " + self.name + " failure " + str(state["failure_count"]) + "/" + str(self.threshold))

        if state["failure_count"] >= self.threshold:
            state["state"] = "OPEN"
            print("Circuit " + self.name + " OPEN! Service blocked!")

        self._save_state(state)

    def get_status(self):
        state = self._get_state()
        return {
            "name": self.name,
            "state": state["state"],
            "failure_count": state["failure_count"],
            "threshold": self.threshold
        }

email_breaker = CircuitBreaker("email")
image_breaker = CircuitBreaker("image")
pdf_breaker = CircuitBreaker("pdf")