# Based on  https://github.com/milesial/Pytorch-UNet
import torch
import torch.nn as nn


def fit(model, trainloader, epochs, start_lr, device, model_path=None, loss_fn=None, weight_decay=1e-5):
    optimizer = torch.optim.Adam(model.parameters(), lr=start_lr, weight_decay=weight_decay)
    if loss_fn is None:
        loss_fn = torch.nn.MSELoss()
    i = 0
    for epoch_i in range(epochs):
        for batch_data in trainloader:
            model.train()
            # load batch on device
            batch = batch_data.to(device)
            # reset gradients from last iteration
            optimizer.zero_grad()
            reconstruction = model(batch)
            loss = loss_fn(reconstruction, batch)
            # calculate gradients and reset the computation graph
            loss.backward()
            # update the internal params (weights, etc.)
            optimizer.step()
            i += 1
        if epoch_i % 5 == 0 and model_path is not None:
            torch.save(model.state_dict(), model_path)
            print(f"{model.name}: Epoch {epoch_i+1}/{epochs} - Iteration {i} - Train loss:{loss.item():.4f},",
                  f"LR: {optimizer.param_groups[0]['lr']}")
    return model


class ConvBn(nn.Module):
    """(convolution => [BN] => LeakyReLU)"""

    def __init__(self, in_channels, out_channels, stride=1, kernel_size=3):
        super().__init__()
        if kernel_size == 3:
            padding = 1
        elif kernel_size == 5:
            padding = 2

        self.conv_bn = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, padding=padding, stride=stride),
            nn.BatchNorm2d(out_channels),
            nn.LeakyReLU(inplace=True)
        )

    def forward(self, x):
        return self.conv_bn(x)


class ConvLeaky(nn.Module):
    """(convolution => LeakyReLU)"""

    def __init__(self, in_channels, out_channels, stride=1, kernel_size=3):
        super().__init__()
        if kernel_size == 3:
            padding = 1
        elif kernel_size == 5:
            padding = 2
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, padding=padding, stride=stride),
            nn.LeakyReLU(inplace=True)
        )

    def forward(self, x):
        return self.conv(x)


class Down(nn.Module):
    """Downscaling double conv and stride"""

    def __init__(self, in_channels, out_channels, kernel_size=3, bn=True):
        super().__init__()
        if bn:
            self.conv = ConvBn(in_channels, out_channels, stride=2, kernel_size=kernel_size)
        else:
            self.conv = ConvLeaky(in_channels, out_channels, stride=2, kernel_size=kernel_size)
    def forward(self, x):
        return self.conv(x)


class Up(nn.Module):
    """Upscaling then conv"""

    def __init__(self, in_channels, out_channels, scale_factor=2, kernel_size=3, bn=True):
        super().__init__()


        self.up = nn.Upsample(scale_factor=scale_factor, mode='bilinear', align_corners=True)
        if bn:
            self.conv = ConvBn(in_channels , out_channels, kernel_size=kernel_size)
        else:
            self.conv = ConvLeaky(in_channels , out_channels, kernel_size=kernel_size)

    def forward(self, x):
        x = self.up(x)
        x = self.conv(x)
        return x


class OutConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        return self.conv(x)


class Flatten(nn.Module):
    """From fastai library:
    Flatten `x` to a single dimension, often used at the end of a model. `full` for rank-1 tensor"""
    def __init__(self, full:bool=False):
        super(Flatten, self).__init__()
        self.full = full
    def forward(self, x): return x.view(-1) if self.full else x.view(x.size(0), -1)


class ConvAE(nn.Module):
    def __init__(self, n_channels, n_classes, embd_sz=128, name="AE"):
        super(ConvAE, self).__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes

        self.inc = ConvBn(n_channels, 128)
        self.down1 = Down(128, 256)
        self.down2 = Down(256, 512)
        factor = 1
        self.down3 = Down(512, 1024// factor)
        enc_dim = 1024 * 4 * 4
        self.flatten = Flatten()
        self.encoder = nn.Sequential(
            nn.Linear(enc_dim, embd_sz*2),
            nn.BatchNorm1d(embd_sz*2),
            nn.LeakyReLU(inplace=True),
            nn.Linear(embd_sz*2, embd_sz),
        )
        self.decoder = nn.Sequential(nn.Linear(embd_sz, enc_dim),
                                     nn.BatchNorm1d(enc_dim),
                                     nn.LeakyReLU(inplace=True),
                                     )
        self.up1 = Up(1024, 512 // factor, scale_factor=2)
        self.up2 = Up(512, 256 // factor)
        self.up3 = Up(256, 128 // factor)

        self.outc = OutConv(128, n_classes)

        self.name = name

    def encode(self,x):
        e = self.inc(x)
        e = self.down1(e)
        e = self.down2(e)
        e = self.down3(e)
        e = self.flatten(e)
        e = self.encoder(e)
        return e

    def decode(self,e):
        d = self.decoder(e)
        d = d.view(-1, 1024, 4,4)
        d = self.up1(d)
        d = self.up2(d)
        d = self.up3(d)
        return self.outc(d)

    def forward(self, x):
        e = self.encode(x)
        d = self.decode(e)
        return d

    def fit(self, trainloader, epochs, start_lr, device, model_path=None, loss_fn=None, weight_decay=1e-5):
        fit(model=self,
            trainloader=trainloader,
            epochs=epochs,
            start_lr=start_lr,
            device=device,
            model_path=model_path,
            loss_fn=loss_fn,
            weight_decay=weight_decay)


class ConvAESmall(nn.Module):
    def __init__(self, n_channels, n_classes, embd_sz=128, kernel_size=3, name="SmallAE"):
        super(ConvAESmall, self).__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes

        self.inc = ConvBn(n_channels, 16, kernel_size=kernel_size)
        self.down1 = Down(16, 16, kernel_size=kernel_size)
        self.down2 = Down(16, 32, kernel_size=kernel_size)
        factor = 1
        self.down3 = Down(32, 32// factor, kernel_size=kernel_size)
        enc_dim = 32 * 4 * 4
        self.flatten = Flatten()
        self.encoder = nn.Sequential(
            nn.Linear(enc_dim, embd_sz),
        )
        self.decoder = nn.Sequential(nn.Linear(embd_sz, enc_dim),
                                     nn.BatchNorm1d(enc_dim),
                                     nn.LeakyReLU(inplace=True),
                                     )
        self.up1 = Up(32, 32 // factor, scale_factor=2, kernel_size=kernel_size)
        self.up2 = Up(32, 16 // factor, kernel_size=kernel_size)
        self.up3 = Up(16, 16 // factor, kernel_size=kernel_size)

        self.outc = OutConv(16, n_classes)
        self.name = name

    def encode(self,x):
        e = self.inc(x)
        e = self.down1(e)
        e = self.down2(e)
        e = self.down3(e)
        e = self.flatten(e)
        e = self.encoder(e)
        return e

    def decode(self,e):
        d = self.decoder(e)
        d = d.view(-1, 32, 4,4)
        d = self.up1(d)
        d = self.up2(d)
        d = self.up3(d)
        return self.outc(d)

    def forward(self, x):
        e = self.encode(x)
        d = self.decode(e)
        return d

    def fit(self, trainloader, epochs, start_lr, device, model_path=None, loss_fn=None, weight_decay=1e-5):
        fit(model=self,
            trainloader=trainloader,
            epochs=epochs,
            start_lr=start_lr,
            device=device,
            model_path=model_path,
            loss_fn=loss_fn,
            weight_decay=weight_decay)



