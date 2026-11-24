def build_optimizer(model):
    learning_rate = 0.001
    batch_size = 32
    seed = 42
    return dict(lr=learning_rate, bs=batch_size, seed=seed)
