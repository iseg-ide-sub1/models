import torch
from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping
from pytorch_lightning.loggers import TensorBoardLogger
from torch.utils.data import random_split

from cfc import CFC
from config import train_params, model_params
from learner import Learner
from dataset import generate_data  # 修改导入


if __name__ == '__main__':
    # 使用整个数据集目录
    dataset_dir = 'dataset'  # 包含所有pt文件的目录
    max_seq_len = model_params['max_seq_len']
    batch_size = train_params['batch_size']
    num_workers = train_params['num_workers']
    
    # 生成数据
    data_x, data_y = generate_data(dataset_dir, max_seq_len)
    print(f'Dataset X shape: {data_x.shape}')  # [样本数, 序列长度, 特征数]
    print(f'Dataset Y shape: {data_y.shape}')  # [样本数, 序列长度]
    
    # 更新模型参数以匹配特征维度
    feature_dim = data_x.shape[-1]  # 获取特征维度
    model_params['in_features'] = feature_dim  # 更新输入特征维度

    # 检查数据集大小
    if data_x.shape[0] < 2:
        raise ValueError(f"Dataset too small: {data_x.shape[0]} samples. Need at least 2 samples for training and validation.")
    
    # 构造dataset
    dataset = torch.utils.data.TensorDataset(data_x, data_y)
    train_size = int(train_params['train_ratio'] * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    train_dataloader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        persistent_workers=True
    )
    val_dataloader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        persistent_workers=True
    )
    
    # 构造模型
    cfc = CFC(
        in_features=model_params['in_features'],  # 使用更新后的特征维度
        out_features=model_params['out_features'],
        units=model_params['units']
    )

    learner = Learner(
        cfc.model,
        lr=train_params['base_lr'],
        decay_lr=train_params['decay_lr'],
        weight_decay=train_params['weight_decay'],
    )
    
    # 配置日志记录器
    logger = TensorBoardLogger('ckpt', name='cfc', version=1, log_graph=True)

    # 配置检查点和早停回调
    checkpoint_callback = ModelCheckpoint(
        dirpath="ckpt/cfc/version_1",
        filename="cfc-best",
        save_top_k=1,
        monitor="val_acc",
        mode="max",
        save_weights_only=True
    )
    
    early_stop_callback = EarlyStopping(
        monitor="val_acc",
        mode="max",
        patience=train_params['early_stop_patience'],
        verbose=True
    )
    
    trainer = Trainer(
        logger=logger,
        max_epochs=train_params['max_epochs'],
        gradient_clip_val=1,
        log_every_n_steps=train_params['log_interval'],
        callbacks=[checkpoint_callback, early_stop_callback]
    )

    # 开始训练
    trainer.fit(
        learner,
        train_dataloaders=train_dataloader,
        val_dataloaders=val_dataloader
    )

    # 打印训练结果
    print(f'Best validation accuracy: {checkpoint_callback.best_model_score:.4f}')