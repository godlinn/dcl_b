import numpy as np
import torchvision


class RotNetTransforms:
    def __init__(self):
        self.train_transform = torchvision.transforms.Compose([
            torchvision.transforms.ToTensor()
        ])
        self.rotate = {0: rotate_0, 1: rotate_90, 2: rotate_180, 3: rotate_270}

    def __call__(self, x):
        rotated_xs = [self.train_transform(r(x)) for _, r in self.rotate.items()]
        rotated_labels = [label for label, _ in self.rotate.items()]
        return rotated_xs, rotated_labels

    def one(self, x):
        return self.train_transform(x)

    def get_tuple(self, x):
        rotated_xs, _ = self(x)
        return tuple(rotated_xs)

def rotate_0(x):
    return x


def rotate_90(x):
    return np.flipud(np.transpose(x, (1, 0, 2))).copy()


def rotate_180(x):
    return np.fliplr(np.flipud(x)).copy()


def rotate_270(x):
    return np.transpose(np.flipud(x), (1, 0, 2)).copy()
