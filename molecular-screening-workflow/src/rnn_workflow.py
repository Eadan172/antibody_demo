#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RNN 分子生成。

生成与训练分开：
- 演示模式复制 demo/data/sample_molecules.csv，不加载 TensorFlow
- 普通生成只加载已经训练好的模型
- 训练需要显式执行 python src/rnn_workflow.py --train
"""

import json
import os

import pandas as pd

from io_utils import read_table, write_table


def run_rnn_generation(config, demo_mode=False):
    """按配置生成分子，并写入 paths['generated']。"""
    print("=" * 60)
    print("步骤1: RNN分子生成")
    print("=" * 60)

    output_path = config["paths"]["generated"]
    num_molecules = int(config.get("num_molecules", 500))

    if demo_mode:
        source = config.get("demo_molecules", "demo/data/sample_molecules.csv")
        print(f"演示模式: 使用示例分子 {source}，不训练、不加载模型")
        table = read_table(source)
        if "SMILES" not in table.columns:
            raise ValueError(f"{source} 缺少 SMILES 列")
        table = table.dropna(subset=["SMILES"]).head(num_molecules)
        smiles = table["SMILES"].astype(str).tolist()
        write_table(pd.DataFrame({"SMILES": smiles}), output_path)
        print(f"写入 {len(smiles)} 个分子 -> {output_path}")
        return smiles

    model_path = config.get("rnn_model", "models/selfies_generator_rnn.keras")
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"未找到 RNN 模型: {model_path}。"
            "请先训练: python src/rnn_workflow.py --train"
        )

    import numpy as np
    import tensorflow as tf

    meta = _load_meta(model_path)
    model = tf.keras.models.load_model(model_path)
    smiles = _generate_molecules(
        model,
        meta["alphabet"],
        num_molecules,
        float(config.get("temperature", 0.7)),
        int(meta["max_len"]),
        np,
    )
    write_table(pd.DataFrame({"SMILES": smiles}), output_path)
    print(f"生成了 {len(smiles)} 个分子 -> {output_path}")
    return smiles


def train_rnn_model(config):
    """用配置中的训练集训练 Bi-LSTM，并保存词表。不会在生成失败时自动调用。"""
    train_data_path = config["rnn_train_data"]
    model_path = config["rnn_model"]
    epochs = int(config.get("epochs", 200))
    batch_size = int(config.get("batch_size", 128))

    print(f"加载训练数据: {train_data_path}")
    frame = read_table(train_data_path)
    if "SMILES" not in frame.columns:
        raise ValueError(f"{train_data_path} 缺少 SMILES 列")

    import numpy as np
    import selfies as sf
    import tensorflow as tf
    from rdkit import Chem
    from tensorflow.keras.preprocessing.sequence import pad_sequences

    def _canonical(smiles):
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            return None
        return Chem.MolToSmiles(mol)

    frame = frame.dropna(subset=["SMILES"]).copy()
    frame["SMILES"] = frame["SMILES"].apply(_canonical)
    frame = frame.dropna(subset=["SMILES"]).reset_index(drop=True)
    frame["SELFIES"] = [sf.encoder(smiles) for smiles in frame["SMILES"]]
    frame = frame.dropna(subset=["SELFIES"]).reset_index(drop=True)
    print(f"有效分子数: {len(frame)}")
    if frame.empty:
        raise ValueError("训练集中没有可用的 SMILES")

    alphabet = list(sf.get_alphabet_from_selfies(frame["SELFIES"]))
    alphabet.append(".")
    token2idx = {token: idx + 1 for idx, token in enumerate(alphabet)}
    vocab_size = len(alphabet) + 1
    max_len = max(len(list(sf.split_selfies(selfie))) for selfie in frame["SELFIES"]) + 5

    prefixes = []
    targets = []
    for selfie in frame["SELFIES"]:
        token_ids = [token2idx.get(token, 0) for token in sf.split_selfies(selfie)]
        for index in range(len(token_ids) - 1):
            prefixes.append(token_ids[: index + 1])
            targets.append(token_ids[index + 1])

    features = pad_sequences(prefixes, maxlen=max_len - 1, padding="post")
    labels = np.array(targets)
    print(f"训练样本数: {len(features)}")

    model = tf.keras.Sequential(
        [
            tf.keras.layers.Embedding(vocab_size, 512, input_length=max_len - 1),
            tf.keras.layers.Bidirectional(
                tf.keras.layers.LSTM(512, return_sequences=True, dropout=0.1)
            ),
            tf.keras.layers.LayerNormalization(),
            tf.keras.layers.Bidirectional(
                tf.keras.layers.LSTM(512, return_sequences=True, dropout=0.1)
            ),
            tf.keras.layers.LayerNormalization(),
            tf.keras.layers.Bidirectional(
                tf.keras.layers.LSTM(256, return_sequences=False, dropout=0.1)
            ),
            tf.keras.layers.LayerNormalization(),
            tf.keras.layers.Dense(512, activation="relu"),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(vocab_size, activation="softmax"),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.0005),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    history = model.fit(
        features,
        labels,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.1,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="accuracy",
                patience=10,
                restore_best_weights=True,
                min_delta=0.001,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="accuracy", factor=0.5, patience=5, min_lr=1e-6
            ),
            tf.keras.callbacks.ModelCheckpoint(
                model_path.replace(".keras", "_best.keras"),
                monitor="accuracy",
                save_best_only=True,
            ),
        ],
        verbose=1,
    )

    parent = os.path.dirname(model_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    model.save(model_path)
    meta = {"alphabet": alphabet, "max_len": int(max_len)}
    with open(_meta_path(model_path), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)

    final_acc = float(history.history["accuracy"][-1])
    performance = {
        "model_type": "Bi-LSTM",
        "final_accuracy": round(final_acc, 4),
        "epochs_trained": len(history.history["loss"]),
        "note": "下一步 token 准确率只描述训练拟合，不代表生成分子的有效性",
    }
    perf_path = model_path.replace(".keras", "_performance.json")
    with open(perf_path, "w", encoding="utf-8") as handle:
        json.dump(performance, handle, ensure_ascii=False, indent=2)
    print(f"模型已保存: {model_path}")
    return model_path


def _meta_path(model_path):
    return model_path.replace(".keras", "_meta.json")


def _load_meta(model_path):
    path = _meta_path(model_path)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"模型缺少词表文件 {path}。请重新训练: python src/rnn_workflow.py --train"
        )
    with open(path, "r", encoding="utf-8") as handle:
        meta = json.load(handle)
    if "alphabet" not in meta or "max_len" not in meta:
        raise ValueError(f"词表文件不完整: {path}")
    return meta


def _generate_molecules(model, alphabet, num_molecules, temperature, max_len, np):
    import selfies as sf
    from rdkit import Chem

    token2idx = {token: idx + 1 for idx, token in enumerate(alphabet)}
    idx2token = {idx: token for token, idx in token2idx.items()}
    pad_len = max(1, int(max_len) - 1)
    generated = []
    start = token2idx.get("[C]", 1)
    attempts = max(num_molecules * 5, num_molecules)

    for _ in range(attempts):
        if len(generated) >= num_molecules:
            break
        sequence = [start]
        try:
            for _step in range(pad_len - 1):
                padded = sequence + [0] * (pad_len - len(sequence))
                preds = model.predict(np.array([padded]), verbose=0)[0]
                if getattr(preds, "ndim", 1) == 2:
                    preds = preds[len(sequence) - 1]
                next_token = _sample_with_temperature(preds, temperature, np)
                if next_token == 0:
                    break
                sequence.append(int(next_token))

            selfie = "".join(idx2token.get(idx, "") for idx in sequence if idx > 0)
            smiles = sf.decoder(selfie)
            mol = Chem.MolFromSmiles(smiles) if smiles else None
            if mol is None:
                continue
            canonical = Chem.MolToSmiles(mol)
            if canonical not in generated:
                generated.append(canonical)
        except Exception:
            continue
    return generated


def _sample_with_temperature(preds, temperature, np):
    preds = np.asarray(preds).astype("float64")
    preds = np.log(preds + 1e-10) / temperature
    exp_preds = np.exp(preds)
    total = np.sum(exp_preds)
    if not np.isfinite(total) or total <= 0:
        return 0
    probs = exp_preds / total
    draw = np.random.multinomial(1, probs, 1)
    return int(np.argmax(draw))


def _config_from_args(args):
    from config_loader import load_raw_config, resolve_config

    raw = load_raw_config(args.config)
    return resolve_config(raw, demo_mode=args.demo)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RNN 分子生成。训练与生成分开。")
    parser.add_argument("--config", default="config/workflow_config.yaml")
    parser.add_argument("--demo", action="store_true", help="使用示例分子，不加载模型")
    parser.add_argument("--train", action="store_true", help="训练模型后退出，不自动生成")
    cli = parser.parse_args()
    resolved = _config_from_args(cli)
    if cli.train:
        train_rnn_model(resolved)
    else:
        run_rnn_generation(resolved, demo_mode=cli.demo)
