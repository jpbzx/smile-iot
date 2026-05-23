#!/usr/bin/env python3
"""
Test script for the new compact MQTT format parser.

Run: python software/test_mqtt_parser.py
"""

import sys
sys.path.insert(0, '/home/bzxs/pesta/pesta-smile-iot/software')

from utils.mqtt_client import _parse_energy_reading


def test_parser():
    """Test the compact format parser."""
    
    print("Testing compact MQTT format parser...\n")
    
    # Test 1: Valid compact format
    print("Test 1: Valid compact format")
    payload = "5.23,5.18,1,5.20"
    result = _parse_energy_reading(payload)
    
    assert result is not None, "Parser returned None for valid input"
    assert result["current_A"] == 5.23, f"Expected 5.23, got {result['current_A']}"
    assert result["precise_A"] == 5.18, f"Expected 5.18, got {result['precise_A']}"
    assert result["state"] == True, f"Expected True, got {result['state']}"
    assert result["avg"] == 5.20, f"Expected 5.20, got {result['avg']}"
    assert result["outlet_state"] == "ON", f"Expected 'ON', got {result['outlet_state']}"
    assert result["power_W"] == 5.18 * 230.0, f"Power calculation incorrect"
    print("✅ Test 1 passed!\n")
    
    # Test 2: State OFF (0)
    print("Test 2: State OFF (0)")
    payload = "2.50,2.45,0,2.47"
    result = _parse_energy_reading(payload)
    
    assert result["state"] == False, "State should be False for 0"
    assert result["outlet_state"] == "OFF", "Outlet state should be OFF"
    print("✅ Test 2 passed!\n")
    
    # Test 3: High current values
    print("Test 3: High current values")
    payload = "25.50,25.48,1,25.49"
    result = _parse_energy_reading(payload)
    
    assert result["current_A"] == 25.50, "High current not parsed correctly"
    assert result["precise_A"] == 25.48, "High precise current not parsed correctly"
    assert result["power_W"] == 25.48 * 230.0, "High power calculation incorrect"
    print("✅ Test 3 passed!\n")
    
    # Test 4: Zero values
    print("Test 4: Zero values")
    payload = "0.00,0.00,0,0.00"
    result = _parse_energy_reading(payload)
    
    assert result["current_A"] == 0.0, "Zero current not handled"
    assert result["state"] == False, "Zero state should be False"
    print("✅ Test 4 passed!\n")
    
    # Test 5: Payload with whitespace
    print("Test 5: Payload with whitespace")
    payload = "  5.23,5.18,1,5.20  "
    result = _parse_energy_reading(payload)
    
    assert result is not None, "Parser should handle whitespace"
    assert result["current_A"] == 5.23, "Whitespace not stripped correctly"
    print("✅ Test 5 passed!\n")
    
    # Test 6: Invalid format - too few fields
    print("Test 6: Invalid format - too few fields")
    payload = "5.23,5.18,1"
    result = _parse_energy_reading(payload)
    
    assert result is None, "Parser should return None for invalid format"
    print("✅ Test 6 passed!\n")
    
    # Test 7: Invalid format - too many fields
    print("Test 7: Invalid format - too many fields")
    payload = "5.23,5.18,1,5.20,extra"
    result = _parse_energy_reading(payload)
    
    assert result is None, "Parser should return None for too many fields"
    print("✅ Test 7 passed!\n")
    
    # Test 8: Invalid format - non-numeric values
    print("Test 8: Invalid format - non-numeric values")
    payload = "abc,5.18,1,5.20"
    result = _parse_energy_reading(payload)
    
    assert result is None, "Parser should return None for non-numeric values"
    print("✅ Test 8 passed!\n")
    
    # Test 9: Invalid format - invalid state (not 0 or 1)
    print("Test 9: Invalid format - invalid state")
    payload = "5.23,5.18,2,5.20"
    result = _parse_energy_reading(payload)
    
    # This should still parse but state will be True (any non-zero is True)
    assert result is not None, "Parser should handle non-standard state values"
    assert result["state"] == True, "Non-zero state should be True"
    print("✅ Test 9 passed!\n")
    
    # Test 10: Empty payload
    print("Test 10: Empty payload")
    payload = ""
    result = _parse_energy_reading(payload)
    
    assert result is None, "Parser should return None for empty payload"
    print("✅ Test 10 passed!\n")
    
    print("=" * 50)
    print("✅ All tests passed successfully!")
    print("=" * 50)
    
    # Performance comparison
    print("\n📊 Performance Comparison:\n")
    
    import json
    import time
    
    # Test with 1000 messages
    num_messages = 1000
    compact_payload = "5.23,5.18,1,5.20"
    json_payload = '{"current_A":5.23,"precise_A":5.18,"state":1,"avg":5.20}'
    
    # Compact format
    start = time.perf_counter()
    for _ in range(num_messages):
        _parse_energy_reading(compact_payload)
    compact_time = time.perf_counter() - start
    
    # JSON format (old way)
    start = time.perf_counter()
    for _ in range(num_messages):
        json.loads(json_payload)
    json_time = time.perf_counter() - start
    
    print(f"Compact format: {compact_time*1000:.2f}ms for {num_messages} messages")
    print(f"JSON format:    {json_time*1000:.2f}ms for {num_messages} messages")
    print(f"Speedup:        {json_time/compact_time:.1f}x faster")
    print(f"\nPayload sizes:")
    print(f"Compact:        {len(compact_payload.encode())} bytes")
    print(f"JSON:           {len(json_payload.encode())} bytes")
    print(f"Reduction:      {(1 - len(compact_payload.encode())/len(json_payload.encode()))*100:.1f}%")


if __name__ == "__main__":
    test_parser()
