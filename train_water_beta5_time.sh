for seed in {1..5}
do 
    python train_water.py --beta 5 --times ${seed}
done


