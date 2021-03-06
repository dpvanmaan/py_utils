import pytest
import matplotlib.pyplot as plt
import numpy as np
from sklearn.datasets import make_blobs
from sklearn.metrics import silhouette_score
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from autoencoder import run_vae, VariationalAutoEncoder

X, y = make_blobs(n_samples=1000, n_features=30, centers=3,
                  random_state=1988)


def test_vae():
    X2 = run_vae(X, latent_dim=20,
                 encoding_dim=2,
                 batch_size=100,
                 compute_error=True,
                 verbose=True)[0]
    si = silhouette_score(X2, y)
    plt.figure()
    plt.scatter(X2[:, 0], X2[:, 1], c=y)
    plt.savefig('vae.png')
    assert si > 0.8, 'Score {} < 0.8'.format(si)
    print('Silhouette score: {}'.format(si))


def test_vae_2():
    X2 = run_vae(X, latent_dim=20,
                 encoding_dim=2,
                 batch_size=128,
                 compute_error=True,
                 verbose=True)[0]
    si = silhouette_score(X2, y[:X2.shape[0]])
    plt.figure()
    plt.scatter(X2[:, 0], X2[:, 1], c=y[:X2.shape[0]])
    plt.savefig('vae2.png')
    assert si > 0.8, 'Score {} < 0.8'.format(si)
    print('Silhouette score: {}'.format(si))


def test_sk_vae():
    sk = VariationalAutoEncoder(layer_dim=20, encoding_dim=2)
    X2 = sk.fit_transform(X)
    si = silhouette_score(X2, y)
    plt.figure()
    plt.scatter(X2[:, 0], X2[:, 1], c=y)
    plt.savefig('skvae.png')
    assert si > 0.8, 'Score {} < 0.8'.format(si)
    print('Silhouette score: {}'.format(si))
