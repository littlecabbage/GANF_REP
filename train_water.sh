for seed in {1..5}
do 
    python -u train_water.py\
        --seed=${seed}\
        --name=GANF_water_seed_${seed}
done


