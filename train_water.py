#%%
from ast import parse
import os
import argparse
import torch
from models.GANF import GANF
import numpy as np
from sklearn.metrics import roc_auc_score,f1_score, precision_score, recall_score
from datetime import datetime


# from data import fetch_dataloaders

import pandas as pd

import sys

class Logger(object):
    def __init__(self, file_name = 'temp.log', stream = sys.stdout) -> None:
        self.terminal = stream
        self.log = open(f'log/{file_name}', "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        pass

# open log handler before print
filename = f"{datetime.now()}"
log_file_name = f"{filename}.log"
sys.stdout = Logger(str(log_file_name))
sys.stderr = Logger(str(log_file_name))

def search_best_f1(label, predict):
    """
    It takes in a list of labels and a list of predictions, and returns the best F1 score, precision,
    and recall, 
    ** along with the threshold that produced the best F1 score **
    
    :param label: the actual labels of the data
    :param predict: the predicted probabilities of the positive class
    """
    f1_best = 0

    best_thr = -float("inf")
    f1_list = []
    pre_list = []
    rec_list = []
    thr_list = []

    thresh_holds = set([round(x, 1) for x in predict])
    for thr in thresh_holds:
        predict_ = [0 if x < thr else 1 for x in predict]
        f1, pre, rec = f1_score(label, predict_), precision_score(label, predict_), recall_score(label, predict_)

        if f1 > f1_best:
            
            f1_best = f1;
            f1_list.append(f1)
            pre_list.append(pre)
            rec_list.append(rec)
            thr_list.append(thr)
            # print(f"Best Threshold: {thr}")
            # print("[f1 = {%.4f}, pre = {%.4f}, rec = {%.4f}]" % (f1, pre, rec))
            best_thr = thr

    

    # return f1_best, f1_list, pre_list, rec_list
    return best_thr, f1_best, pre_list[-1], rec_list[-1]



parser = argparse.ArgumentParser()
# files
parser.add_argument('--data_dir', type=str, 
                    default='./data/SWaT_Dataset_Attack_v0.csv', help='Location of datasets.')
parser.add_argument('--output_dir', type=str, 
                    default='./checkpoint/model')
parser.add_argument('--name',default='GANF_Water')
# restore
parser.add_argument('--graph', type=str, default='None')
parser.add_argument('--model', type=str, default='None')
parser.add_argument('--seed', type=int, default=18, help='Random seed to use.')
# made parameters
parser.add_argument('--n_blocks', type=int, default=1, help='Number of blocks to stack in a model (MADE in MAF; Coupling+BN in RealNVP).')
parser.add_argument('--n_components', type=int, default=1, help='Number of Gaussian clusters for mixture of gaussians models.')
parser.add_argument('--hidden_size', type=int, default=32, help='Hidden layer size for MADE (and each MADE block in an MAF).')
parser.add_argument('--n_hidden', type=int, default=1, help='Number of hidden layers in each MADE.')
parser.add_argument('--batch_norm', type=bool, default=False)
# training params
parser.add_argument('--batch_size', type=int, default=512)
parser.add_argument('--weight_decay', type=float, default=5e-4)
parser.add_argument('--n_epochs', type=int, default=1)
parser.add_argument('--lr', type=float, default=2e-3, help='Learning rate.')
parser.add_argument('--log_interval', type=int, default=5, help='How often to show loss statistics and save samples.')

parser.add_argument('--h_tol', type=float, default=1e-4)
parser.add_argument('--rho_max', type=float, default=1e16)
parser.add_argument('--max_iter', type=int, default=20)
parser.add_argument('--lambda1', type=float, default=0.0)
parser.add_argument('--rho_init', type=float, default=1.0)
parser.add_argument('--alpha_init', type=float, default=0.0)
parser.add_argument('--beta', type = int, default=0)
parser.add_argument('--times', type = int, default=0)

args = parser.parse_known_args()[0]
args.cuda = torch.cuda.is_available()
device = torch.device("cuda" if args.cuda else "cpu")


print(args)
import random
import numpy as np
random.seed(args.seed)
np.random.seed(args.seed)
torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)
#%%
print(f"Loading dataset  beta = {args.beta}  times = {args.times}")
from get_all_dataset import load_water

train_loader, val_loader, test_loader, n_sensor = load_water(args.data_dir, \
                                                                args.batch_size, beta = args.beta, times = args.times)
#%%

rho = args.rho_init # default = 1.0
alpha = args.alpha_init # default = 0.0
lambda1 = args.lambda1 # default = 0.0
h_A_old = np.inf 


max_iter = args.max_iter # default = 20
rho_max = args.rho_max # default = 1e16
h_tol = args.h_tol # default = 1e-4
epoch = 0

# initialize A
if args.graph != 'None':
    init = torch.load(args.graph).to(device).abs() # default = None
    print("Load graph from "+args.graph)
else:
    from torch.nn.init import xavier_uniform_
    init = torch.zeros([n_sensor, n_sensor])
    init = xavier_uniform_(init).abs()
    init = init.fill_diagonal_(0.0)
A = torch.tensor(init, requires_grad=True, device=device)

#%%
model = GANF(args.n_blocks, 1, args.hidden_size, args.n_hidden, dropout=0.0, batch_norm=args.batch_norm) # default batch_norma = False
model = model.to(device)
print(model)
if args.model != 'None':
    model.load_state_dict(torch.load(args.model))
    print('Load model from '+args.model)
#%%
from torch.nn.utils import clip_grad_value_
import seaborn as sns
import matplotlib.pyplot as plt
save_path = os.path.join(args.output_dir,args.name)
if not os.path.exists(save_path):
    os.makedirs(save_path)



loss_best = 100

for _ in range(max_iter):

    while rho < rho_max:
        lr = args.lr 
        optimizer = torch.optim.Adam([
            {'params':model.parameters(), 'weight_decay':args.weight_decay},
            {'params': [A]}], lr=lr, weight_decay=0.0)
        
        for _ in range(args.n_epochs): # default = 1

            # train iteration
            loss_train = []
            epoch += 1
            model.train()
            for x in train_loader:
                x = x.to(device)

                optimizer.zero_grad()
                loss = -model(x,  A)
                h = torch.trace(torch.matrix_exp( A* A)) - n_sensor
                total_loss = loss + 0.5 * rho * h * h + alpha * h

                total_loss.backward()
                clip_grad_value_(model.parameters(), 1)
                optimizer.step()
                loss_train.append(loss.item())
                A.data.copy_(torch.clamp(A.data, min=0, max=1))
                
            
            # evaluate iteration
            model.eval()
            loss_val = []
            with torch.no_grad():
                for x in val_loader:

                    x = x.to(device)
                    loss = -model.test(x, A.data).cpu().numpy()
                    loss_val.append(loss)
            loss_val = np.concatenate(loss_val)

            loss_test = []
            with torch.no_grad():
                for x in test_loader:

                    x = x.to(device)
                    loss = -model.test(x, A.data).cpu().numpy()
                    loss_test.append(loss)
            loss_test = np.concatenate(loss_test)

            print(loss_val.max(), loss_val.min(), loss_test.max(), loss_test.min())

            loss_val = np.nan_to_num(loss_val)
            loss_test = np.nan_to_num(loss_test)
            roc_val = roc_auc_score(np.asarray(val_loader.dataset.label.values,dtype=int),loss_val)
            roc_test = roc_auc_score(np.asarray(test_loader.dataset.label.values,dtype=int),loss_test)
            print('Epoch: {}, train -log_prob: {:.2f}, test -log_prob: {:.2f}, roc_val: {:.4f}, roc_test: {:.4f} ,h: {}'\
                    .format(epoch, np.mean(loss_train), np.mean(loss_val), roc_val, roc_test, h.item()))
            
            
            best_thr, f1_best, pre, rec = search_best_f1(np.asarray(val_loader.dataset.label.values,dtype=int),loss_val)
            print("[Best Threshold: {%.4f} f1 = {%.4f}, pre = {%.4f}, rec = {%.4f}]" % (best_thr, f1_best, pre, rec))
    
        print('rho: {}, alpha {}, h {}'.format(rho, alpha, h.item()))
        print('===========================================')

        
        torch.save(A.data,os.path.join(save_path, "graph_{}.pt".format(epoch)))
        torch.save(model.state_dict(), os.path.join(save_path, "{}_{}.pt".format(args.name, epoch)))

        del optimizer
        torch.cuda.empty_cache()
        
        if h.item() > 0.5 * h_A_old:
            rho *= 10
        else:
            break


    h_A_old = h.item()
    alpha += rho*h.item()

    if h_A_old <= h_tol or rho >=rho_max:
        break


# %%
lr = args.lr 
optimizer = torch.optim.Adam([
    {'params':model.parameters(), 'weight_decay':args.weight_decay},
    {'params': [A]}], lr=lr, weight_decay=0.0)

for _ in range(30):
    loss_train = []
    epoch += 1
    model.train()
    for x in train_loader:
        x = x.to(device)

        optimizer.zero_grad()
        loss = -model(x, A)
        h = torch.trace(torch.matrix_exp(A*A)) - n_sensor
        total_loss = loss + 0.5 * rho * h * h + alpha * h 

        total_loss.backward()
        clip_grad_value_(model.parameters(), 1)
        optimizer.step()
        loss_train.append(loss.item())
        A.data.copy_(torch.clamp(A.data, min=0, max=1))

    # eval 
    model.eval()
    loss_val = []
    with torch.no_grad():
        for x in val_loader:

            x = x.to(device)
            loss = -model.test(x, A.data).cpu().numpy()
            loss_val.append(loss)
    loss_val = np.concatenate(loss_val)

    loss_test = []
    with torch.no_grad():
        for x in test_loader:

            x = x.to(device)
            loss = -model.test(x, A.data).cpu().numpy()
            loss_test.append(loss)
    loss_test = np.concatenate(loss_test)

    loss_val = np.nan_to_num(loss_val)
    loss_test = np.nan_to_num(loss_test)
    roc_val = roc_auc_score(np.asarray(val_loader.dataset.label.values,dtype=int),loss_val)
    roc_test = roc_auc_score(np.asarray(test_loader.dataset.label.values,dtype=int),loss_test)
    print('Epoch: {}, train -log_prob: {:.2f}, test -log_prob: {:.2f}, roc_val: {:.4f}, roc_test: {:.4f} ,h: {}'\
            .format(epoch, np.mean(loss_train), np.mean(loss_val), roc_val, roc_test, h.item()))
    
    best_thr, f1_best, pre, rec = search_best_f1(np.asarray(val_loader.dataset.label.values,dtype=int),loss_val)
    print("[Best Threshold: {%.4f} f1 = {%.4f}, pre = {%.4f}, rec = {%.4f}]" % (best_thr, f1_best, pre, rec))

    if np.mean(loss_val) < loss_best:
        loss_best = np.mean(loss_val)
        print("save model {} epoch".format(epoch))
        torch.save(A.data,os.path.join(save_path, "graph_best.pt"))
        torch.save(model.state_dict(), os.path.join(save_path, "{}_best.pt".format(args.name)))

    if epoch % args.log_interval==0:
        torch.save(A.data,os.path.join(save_path, "graph_{}.pt".format(epoch)))
        torch.save(model.state_dict(), os.path.join(save_path, "{}_{}.pt".format(args.name, epoch)))