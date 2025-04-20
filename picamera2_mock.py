"""
Mock picamera2 module for local testing
"""
class Picamera2:
    def __init__(self):
        print("Mock Picamera2 initialized")
        
    def configure(self, config):
        print("Mock camera configured")
        
    def create_video_configuration(self):
        return {}
        
    def start(self):
        print("Mock camera started")
        
    def stop(self):
        print("Mock camera stopped")
        
    def create_encoder(self):
        encoder = MockEncoder()
        return encoder

class MockEncoder:
    def __init__(self):
        self.output = None
        
    def start(self):
        print(f"Mock encoder started: {self.output}")
        # Create a dummy file
        with open(self.output, 'wb') as f:
            f.write(b'dummy video content')
            
    def stop(self):
        print("Mock encoder stopped")
