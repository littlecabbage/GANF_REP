
from typing_extensions import dataclass_transform
import torchvision
from torch.utils.data import DataLoder


# prepare dataset
train_data = torchvision.datasets.CIFAR10(root="../data", train=True, transform=torchvision.transforms.ToTensor(),download=True)

test_data = torchvision.datasets.CIFAR10(root="../data", train=False, transform=torchvision.transforms.ToTensor(),download=True)

train_data_size = len(train_data)
test_data_size = len(test_data)

print(f"Train Data: {train_data_size}, Test data: {test_data_size}")

# DataLoader for Loading data..
train_data_loader = DataLoder(train_data, batch_size = 64)
