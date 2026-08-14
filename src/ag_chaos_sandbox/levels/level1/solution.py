import asyncio
import websockets
import json
import sys

# Level 1 Solution: Programmatically clear all targets without losing HP
# This relies on the backend `env_rules` (Ontology) to maintain safe standoff
# during aiming, and us firing the right action at the right distance.

async def student_solution():
    uri = "ws://127.0.0.1:8765/ws"

    try:
        async with websockets.connect(uri) as ws:
            print("Connected to Ag-Chaos Sandbox...")

            # Reset environment
            await ws.send("Reset")
            await asyncio.sleep(2)

            # Action Plan for 3 tomatoes
            actions = ["Spray", "Cut", "Spray"]

            for i in range(3):
                print(f"\n--- Targeting Tomato {i} ---")
                await ws.send(f"Target:{i}")

                # Wait for IK to settle
                await asyncio.sleep(3)

                # Execute valid action based on rules
                action = actions[i]
                print(f"Executing: {action}")
                await ws.send(action)

                # Wait for action effect
                await asyncio.sleep(2)

            # Return home
            print("\n--- Returning Home ---")
            await ws.send("Target:-1")
            await asyncio.sleep(2)

            print("\n--- Final Status Request ---")
            # Wait for one state update to read HP
            state_str = await ws.recv()
            state = json.loads(state_str)

            env_rules_hp = state['env_rules']['tomato_hp']
            env_no_rules_hp = state['env_no_rules']['tomato_hp']

            print(f"Final HP (With Ontology): {env_rules_hp} (Expected > 100)")
            print(f"Final HP (No Ontology): {env_no_rules_hp} (Expected < 100 due to collisions)")

            if env_rules_hp >= 100:
                print("\n✅ SUCCESS: Level 1 completed perfectly!")
            else:
                print("\n❌ FAILED: HP dropped during execution.")

    except ConnectionRefusedError:
        print("Error: Could not connect to the server. Is it running?")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(student_solution())
