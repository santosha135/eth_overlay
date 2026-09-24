package main

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"time"

	"github.com/ethereum/go-ethereum/src/bucket"
)

// ================================================================
// CONFIGURATION
// ================================================================

const (
	// Keep the number of miners in each bucket constant.
	minersPerBucket = 6

	// Rotate every block.
	rotationBlocks = uint64(1)

	// Number of independent experimental runs.
	independentRuns = 5

	// Operations measured together in one batch.
	callsPerBatch = 10000

	// Number of timed batches for each miner.
	batches = 1000

	// Warm-up operations before timing.
	warmupCalls = 100000
)

// Prevent compiler optimization.
var rotationSink int
var epochSink uint64

// ================================================================
// MAIN
// ================================================================

func main() {

	// ============================================================
	// SCALABILITY VARIABLE
	// ============================================================

	bucketCounts := []int{
		5,
		10,
		15,
		30,
		50,
		100,
	}

	fmt.Println("============================================================")
	fmt.Println("BUCKET ROTATION SCALABILITY BENCHMARK")
	fmt.Println("============================================================")

	fmt.Printf("Miners per bucket : %d\n", minersPerBucket)
	fmt.Printf("Rotation blocks    : %d\n", rotationBlocks)
	fmt.Printf("Independent runs   : %d\n", independentRuns)
	fmt.Printf("Calls per batch    : %d\n", callsPerBatch)
	fmt.Printf("Batches per miner  : %d\n", batches)
	fmt.Printf("Warm-up calls      : %d\n", warmupCalls)

	fmt.Println()
	fmt.Println("Scalability configurations:")
	fmt.Println()

	for _, numBuckets := range bucketCounts {

		totalMiners :=
			numBuckets * minersPerBucket

		fmt.Printf(
			"  %3d buckets x %d miners/bucket = %3d total miners\n",
			numBuckets,
			minersPerBucket,
			totalMiners,
		)
	}

	// ============================================================
	// FIVE INDEPENDENT RUNS
	// ============================================================

	for run := 1; run <= independentRuns; run++ {

		runDir := fmt.Sprintf(
			"run_%02d",
			run,
		)

		err := os.MkdirAll(
			runDir,
			0755,
		)

		if err != nil {
			panic(err)
		}

		fmt.Println()
		fmt.Println("============================================================")
		fmt.Printf(
			"INDEPENDENT RUN %d / %d\n",
			run,
			independentRuns,
		)
		fmt.Println("============================================================")

		// ========================================================
		// TEST EACH BUCKET CONFIGURATION
		// ========================================================

		for _, numBuckets := range bucketCounts {

			totalMiners :=
				numBuckets * minersPerBucket

			fmt.Println()
			fmt.Println(
				"------------------------------------------------------------",
			)

			fmt.Printf(
				"Independent run : %d\n",
				run,
			)

			fmt.Printf(
				"Buckets         : %d\n",
				numBuckets,
			)

			fmt.Printf(
				"Miners/bucket   : %d\n",
				minersPerBucket,
			)

			fmt.Printf(
				"Total miners    : %d\n",
				totalMiners,
			)

			fmt.Println(
				"------------------------------------------------------------",
			)

			// GC before configuration.
			// GC is outside the timed region.
			runtime.GC()

			runRotationBenchmark(
				run,
				runDir,
				numBuckets,
				totalMiners,
			)
		}
	}

	// Make results observable.
	runtime.KeepAlive(rotationSink)
	runtime.KeepAlive(epochSink)

	fmt.Println()
	fmt.Println("============================================================")
	fmt.Println("ALL BUCKET ROTATION BENCHMARKS FINISHED")
	fmt.Println("============================================================")
}

// ================================================================
// BUCKET ROTATION BENCHMARK
// ================================================================

func runRotationBenchmark(
	run int,
	runDir string,
	numBuckets int,
	totalMiners int,
) {

	// ============================================================
	// OUTPUT FILE
	// ============================================================

	filename := filepath.Join(
		runDir,
		fmt.Sprintf(
			"bucket_rotation_%d_buckets.csv",
			numBuckets,
		),
	)

	file, err := os.Create(filename)

	if err != nil {
		panic(err)
	}

	defer file.Close()

	writer := csv.NewWriter(file)

	defer writer.Flush()

	// ============================================================
	// CSV HEADER
	// ============================================================

	err = writer.Write([]string{
		"independent_run",
		"batch",
		"num_buckets",
		"miners_per_bucket",
		"total_miners",
		"miner_index",
		"group_id",
		"member_index",
		"group_size",
		"calls_per_batch",
		"start_block",
		"total_duration_ns",
		"duration_ns_per_call",
	})

	if err != nil {
		panic(err)
	}

	fmt.Printf(
		"\nBucket rotation benchmark started:\n"+
			"  Run           = %d\n"+
			"  Buckets       = %d\n"+
			"  Miners/bucket = %d\n"+
			"  Total miners  = %d\n",
		run,
		numBuckets,
		minersPerBucket,
		totalMiners,
	)

	// ============================================================
	// EVERY MINER
	// ============================================================

	for minerIndex := 0;
		minerIndex < totalMiners;
		minerIndex++ {

		// --------------------------------------------------------
		// ASSIGN MINER TO BUCKET
		// --------------------------------------------------------

		groupID,
			memberIndex,
			groupSize :=
			bucket.BuildMinerGroupAssignment(
				minerIndex,
				totalMiners,
				numBuckets,
			)

		// ========================================================
		// SANITY CHECK
		// ========================================================

		if groupSize != minersPerBucket {

			panic(
				fmt.Sprintf(
					"Unexpected group size: "+
						"run=%d buckets=%d miner=%d "+
						"expected=%d got=%d",
					run,
					numBuckets,
					minerIndex,
					minersPerBucket,
					groupSize,
				),
			)
		}

		// --------------------------------------------------------
		// CREATE SCHEDULER
		// --------------------------------------------------------

		scheduler :=
			bucket.NewScheduler(
				numBuckets,
				groupID,
				rotationBlocks,
			)

		fmt.Printf(
			"Miner %3d -> "+
				"group=%3d "+
				"member=%d "+
				"groupSize=%d\n",
			minerIndex,
			groupID,
			memberIndex,
			groupSize,
		)

		// ========================================================
		// WARM-UP
		// ========================================================

		for i := 1;
			i <= warmupCalls;
			i++ {

			blockNumber :=
				uint64(i)

			scheduler.SetHeadBlock(
				blockNumber,
			)

			epochSink =
				scheduler.Epoch()

			rotationSink =
				scheduler.ActiveBucket()
		}

		// ========================================================
		// TIMED BATCHES
		// ========================================================

		for batch := 0;
			batch < batches;
			batch++ {

			startBlock :=
				uint64(
					batch*callsPerBatch + 1,
				)

			// ====================================================
			// TIMER START
			// ====================================================

			start := time.Now()

			for j := 0;
				j < callsPerBatch;
				j++ {

				blockNumber :=
					startBlock +
						uint64(j)

				// -----------------------------------------------
				// BUCKET ROTATION OPERATIONS
				// -----------------------------------------------

				scheduler.SetHeadBlock(
					blockNumber,
				)

				epochSink =
					scheduler.Epoch()

				rotationSink =
					scheduler.ActiveBucket()
			}

			// ====================================================
			// TIMER STOP
			// ====================================================

			elapsed :=
				time.Since(start)

			totalDurationNS :=
				elapsed.Nanoseconds()

			nsPerCall :=
				float64(totalDurationNS) /
					float64(callsPerBatch)

			// ====================================================
			// WRITE CSV OUTSIDE TIMED REGION
			// ====================================================

			err := writer.Write([]string{

				strconv.Itoa(run),

				strconv.Itoa(batch),

				strconv.Itoa(
					numBuckets,
				),

				strconv.Itoa(
					minersPerBucket,
				),

				strconv.Itoa(
					totalMiners,
				),

				strconv.Itoa(
					minerIndex,
				),

				strconv.Itoa(
					groupID,
				),

				strconv.Itoa(
					memberIndex,
				),

				strconv.Itoa(
					groupSize,
				),

				strconv.Itoa(
					callsPerBatch,
				),

				strconv.FormatUint(
					startBlock,
					10,
				),

				strconv.FormatInt(
					totalDurationNS,
					10,
				),

				strconv.FormatFloat(
					nsPerCall,
					'f',
					6,
					64,
				),
			})

			if err != nil {
				panic(err)
			}
		}
	}

	// ============================================================
	// FLUSH CSV
	// ============================================================

	writer.Flush()

	if err := writer.Error(); err != nil {
		panic(err)
	}

	fmt.Printf(
		"\nRun %d | %d buckets | %d miners/bucket | "+
			"%d total miners finished\n",
		run,
		numBuckets,
		minersPerBucket,
		totalMiners,
	)

	fmt.Printf(
		"Saved -> %s\n",
		filename,
	)
}