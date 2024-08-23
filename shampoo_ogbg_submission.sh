
python scoring/run_workloads.py --framework pytorch \
--experiment_name shampoo_ogbg_experiment \
--num_studies 3 \
--num_tuning_trials 5 \
--seed 10 \
--hparam_start_index 1 \
--hparam_end_index 2 \
--run_percentage 100 \
--workload_metadata_path "scoring/workload_metadata_external_tuning.json" \
--submission_path  "submissions/submissions_algorithms_v0_5/AlgoPerf_Team_21/external_tuning/shampoo_submission/submission.py" \
--tuning_search_space "submissions/submissions_algorithms_v0_5/AlgoPerf_Team_21/external_tuning/shampoo_submission/tuning_search_space.json" \
--docker_image_url "us-central1-docker.pkg.dev/training-algorithms-external/mlcommons-docker-repo/algoperf_both_main" --local --workload "ogbg"
