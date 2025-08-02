import requests
import json
# import time # This import was not used

# Define the ngrok URL as a constant
NGROK_URL = "https://7f53-35-186-162-107.ngrok-free.app"  # Replace with your actual URL

def test_colab_flask_endpoint():  # ngrok_url parameter removed
    """Test the Colab Flask retrieval endpoint"""

    # Remove trailing slash if present
    base_url = NGROK_URL.rstrip('/')  # Use the module-level constant
    endpoint = f"{base_url}/enhanced_retrieve"

    # Test payload
    test_payload = {
        "query": "compare M&M vs TCS MD&A financial performance?"
    }

    print(f"Testing endpoint: {endpoint}")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")

    try:
        headers = {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
        }

        response = requests.post(
            endpoint,
            json=test_payload,
            headers=headers,
            timeout=30
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"Context length: {len(result.get('context', ''))}")
            print(f"NER entities: {result.get('ner_entities', [])}")
            print(f"Number of chunks: {result.get('num_chunks', 0)}")
            print(response.text)
            # Add assertions for pytest to check conditions
            assert result.get('context') is not None, "Context should not be None"
            # return True # Not strictly necessary for pytest if assertions pass
        else:
            print("❌ FAILED!")
            print(f"Response text: {response.text}")
            # Make pytest fail if the status code is not 200
            assert False, f"API call failed with status {response.status_code}: {response.text}"
            # return False

    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {e}")
        # Make pytest fail on request exceptions
        assert False, f"RequestException: {e}"
        # return False

# This block allows running the script directly (e.g., `python backend/ngoktets.py`)
# Pytest will discover and run the test_colab_flask_endpoint function independently.
if __name__ == "__main__":
    test_colab_flask_endpoint()