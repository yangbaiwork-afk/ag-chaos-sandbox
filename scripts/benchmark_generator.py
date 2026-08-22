import timeit
import importlib

def run_benchmark(level_name, iterations=10000):
    try:
        generator = importlib.import_module(f"ag_chaos_sandbox.levels.{level_name}.generator")
    except ImportError:
        print(f"Skipping {level_name}: module not found")
        return

    # Warmup
    generator.generate_procedural_plant_xml()

    timer = timeit.Timer(stmt="generator.generate_procedural_plant_xml()", globals={"generator": generator})

    # Run benchmark
    times = timer.repeat(repeat=5, number=iterations)
    best_time = min(times)

    print(f"{level_name} - Best time for {iterations} iterations: {best_time:.4f} seconds")

if __name__ == "__main__":
    print("Running benchmarks for procedural plant XML generation...")
    run_benchmark("level1")
    run_benchmark("level2")
    run_benchmark("level3")
