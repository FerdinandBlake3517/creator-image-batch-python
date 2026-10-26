from src.creator_batch import CreatorBatchService, CreatorImage, DeliveryUpdate


class FakeClient:
    def __init__(self):
        self.published = []

    def queue_publish(self, queue, payload):
        self.published.append((queue, payload))
        return {"ok": True, "data": {"accepted": True}}

    def image_batch_status(self, batch_id):
        return {"ok": True, "data": {"status": "completed"}}


def test_completed_batch_is_the_only_state_sent_to_subscriber():
    client = FakeClient()
    service = CreatorBatchService(client)
    request_id = service.enqueue(CreatorImage("subscriber-7", "uploads/7.jpg"))
    updates = []

    delivered = service.deliver_updates(
        [DeliveryUpdate("subscriber-7", "batch-7", "processing")], updates.append
    )

    assert delivered == 1
    assert updates == [DeliveryUpdate("subscriber-7", "batch-7", "completed")]
    assert client.published[0][0] == "creator-image-jobs"
    assert client.published[0][1]["subscriber_id"] == "subscriber-7"
    assert client.published[0][1]["request_id"] == request_id
