# Imports
import matplotlib.pyplot as plt
import numpy as np
import torch
import torchvision.datasets as datasets  # Standard datasets
import torchvision.transforms as transforms  # Transformations we can perform on our dataset for augmentation
from torch.utils.data import Dataset

import my_utils as my

import matplotlib.pyplot as plt
import numpy as np
import torch.optim.lr_scheduler as lr_scheduler
from torch import nn
from torch import optim
from torch.utils.data import DataLoader
from tqdm import tqdm
from bayes_opt import BayesianOptimization
import copy



device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Check the accuracy of entire dataset
def check_accuracy(loader, model):
    num_correct = 0
    num_samples = 0
    model.eval()

    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            y = y.to(device)
            # if img_quant_flag == 1:
            #     x, _ = my.data_quantization_sym(x, half_level = img_half_level)
            scores = model(x)
            _, predictions = scores.max(1)
            num_correct += (predictions == y).sum()
            num_samples += predictions.size(0)

    model.train()
    return num_correct / num_samples * 100

def save_model(model, PATH):
    torch.save(model.state_dict(), PATH)
    print('model saved !')


def load_model(model, PATH):
    checkpoint = torch.load(PATH, map_location = "cuda")
    model.load_state_dict(checkpoint, strict = False)
    print('model loaded !')

# Extract number of [examples] data from the given [train_dataset]
# Quant the data
def extract_dataset(train_dataset, img_half_level, examples = 100):
    idx = 0
    imgs = []
    labels = []
    for data, targets in train_dataset:
        # Get data to cuda if possible
        imgs.append(data.unsqueeze(dim = 0))
        labels.append(torch.tensor([targets]))
        idx += 1
        if idx == examples:
            break
    imgs = torch.cat(imgs, dim = 0)
    labels = torch.cat(labels, dim = 0)
    imgs_quant, _ = my.data_quantization_sym(imgs, half_level = img_half_level)
    np.save(f'dataset_imgs_{examples}.npy', imgs_quant.numpy())
    np.save(f'dataset_labels_{examples}.npy', labels.numpy())
    return imgs, labels

# Load the extracted dataset
class custom_dataset(Dataset):
    def __init__(self, data_tensor, target_tensor):
        self.data_tensor = data_tensor
        self.target_tensor = target_tensor

    def __getitem__(self, index):
        return self.data_tensor[index], self.target_tensor[index]

    def __len__(self):
        return self.data_tensor.size(0)

# Print an quantized image
def show_img(train_loader, img_half_level, show_quantized_flag = 1):
    img = iter(train_loader).next()[0][0][0]
    img_quant, _ = my.data_quantization_sym(img, half_level = img_half_level)
    img = img.numpy()
    img_quant = img_quant.numpy()
    if show_quantized_flag == 1:
        plt.subplot(1, 2, 1)
        plt.imshow(img, cmap = 'gray')
        plt.axis('off')
        plt.title('origin')
        plt.subplot(1, 2, 2)
        plt.imshow(img_quant, cmap = 'gray')
        plt.axis('off')
        plt.title('quantized')
        plt.pause(0.001)
    else:
        plt.imshow(img, cmap = 'gray')
        plt.axis('off')


def train_net(model, train_loader, test_loader, criterion, optimizer, epoch_num, scheduler = None, plot_flag=0):
    # Train Network
    # model_max = copy.deepcopy(model.state_dict())
    accuracy_max = 0
    accuracy = 0
    LR = []
    loss_plt = []
    # accuracy_plt = []
    for epoch in range(epoch_num):
        print(f'Epoch = {epoch}')
        loop = tqdm(train_loader, leave=True)
        for (data, targets) in loop:
            # Get data to cuda if possible
            data = data.to(device)
            targets = targets.to(device)

            # # convert to 1bit image
            # if img_quant_flag == 1:
            #     data, _ = my.data_quantization_sym(data, half_level = img_half_level)

            scores = model(data)

            loss = criterion(scores, targets)

            # backward
            optimizer.zero_grad()
            loss.backward()

            # gradient descent or adam step
            optimizer.step()
            if scheduler != None:
                # 如果使用ReduceLROnPlateau，执行下面一行代码
                scheduler.step(loss)

                # 如果使用CosineAnnealingLR，执行下面一行代码
                # scheduler.step()
                # pass
            accuracy = (sum(scores.argmax(dim = 1) == targets) / len(targets)).item() * 100

            lr_current = optimizer.param_groups[0]['lr']
            loop.set_postfix(
                accuracy = accuracy,
                loss = loss.item(),
                LR = lr_current
            )
            LR.append(lr_current)
            loss_plt.append(loss.item())
            # if lr_current == LR_Adam_min:
            #     min_LR_iter -= 1
            #     if min_LR_iter <= 0:
            #         break
            # if accuracy >= accuracy_max:
            #     accuracy_max = accuracy
            #     model_max = copy.deepcopy(model)
        if plot_flag == 1:
            # if epoch % 10 == 0:
            plt.plot(LR)
            plt.show()
            plt.plot(loss_plt)
            plt.show()
        
        
        accuracy_test = check_accuracy(test_loader, model)
        print(f"Accuracy on test set: {accuracy_test:.2f}")

    return model#_max



if __name__ == '__main__':
    img_half_level = 7
    data_num = 10000
    # Load Data
    train_dataset = datasets.FashionMNIST(root = "dataset/", train = True,
                                          transform = transforms.Compose([transforms.ToTensor()]),
                                          download = True)
    test_dataset = datasets.FashionMNIST(root = "dataset/", train = False,
                                         transform = transforms.Compose([transforms.ToTensor()]),
                                         download = True)
    # save custom_dataset as np arrays
    custom_dataset_imgs, custom_dataset_labels = extract_dataset(test_dataset, img_half_level, data_num)
