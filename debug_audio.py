import pyaudio
import json

def main():
    p = pyaudio.PyAudio()
    
    print("\n=== Host APIs ===")
    for i in range(p.get_host_api_count()):
        api_info = p.get_host_api_info_by_index(i)
        print(f"API {i}: {api_info['name']} (Devices: {api_info['deviceCount']})")
        
        print(f"  Devices for API {i}:")
        for j in range(api_info['deviceCount']):
            try:
                dev = p.get_device_info_by_host_api_device_index(i, j)
                print(f"    Dev {j}: {dev['name']}")
                print(f"      Input Channels: {dev['maxInputChannels']}")
                print(f"      Output Channels: {dev['maxOutputChannels']}")
                print(f"      Default Sample Rate: {dev['defaultSampleRate']}")
                print(f"      Index: {dev['index']}")
            except Exception as e:
                print(f"    Dev {j}: Error getting info - {e}")

    p.terminate()

if __name__ == "__main__":
    main()
