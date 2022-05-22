for seed in {1..5}
do 
    python train_water.py --beta 3 --times ${seed}
done


