docker run -it --rm \
    -v /path/to/your/project/submissions:/submissions \
    -v /path/to/your/test_script:/scripts \
    us-central1-docker.pkg.dev/training-algorithms-external/mlcommons-docker-repo/algoperf_both_main \
    python /algorithmic_efficiency/test_module.py
