from keras.layers import Input, Dense, Dropout, Lambda
from keras.models import Model
from keras import regularizers
from keras import backend as K
from keras import metrics
from keras.engine.topology import Layer

from logger import make_logger
from keras.callbacks import TensorBoard

log = make_logger('autoencoder')


def build_vae(input_dim, ngpu=1, layers_dim=[100, 10, 10],
              activations=['tanh', 'tanh'],
              inits=['glorot_uniform', 'glorot_normal'],
              optimizer='adam', batch_size=512,
              drop=0.1, l2=1e-5,
              loss='mse', epsilon_std=1):

    x = Input(batch_shape=(batch_size, input_dim))
    h = Dense(layers_dim[0], activation='relu')(x)

    z_mean = Dense(layers_dim[-1])(h)
    z_log_var = Dense(layers_dim[-1])(h)

    def sampling(args):
        z_mean, z_log_var = args
        epsilon = K.random_normal(shape=(batch_size, layers_dim[-1]),
                                  mean=0., stddev=epsilon_std)
        return z_mean + K.exp(z_log_var / 2) * epsilon

    z = Lambda(sampling)([z_mean, z_log_var])

    decoder_h = Dense(layers_dim[0], activation='relu')
    decoder_mean = Dense(input_dim, activation='sigmoid')
    h_decoded = decoder_h(z)
    x_decoded_mean = decoder_mean(h_decoded)

    # Custom loss layer
    class CustomVariationalLayer(Layer):
        def __init__(self, **kwargs):
            self.is_placeholder = True
            super(CustomVariationalLayer, self).__init__(**kwargs)

        def vae_loss(self, x, x_decoded_mean):
            xent_loss = input_dim * \
                metrics.binary_crossentropy(x, x_decoded_mean)
            kl_loss = - 0.5 * K.sum(1 + z_log_var -
                                    K.square(z_mean) - K.exp(z_log_var),
                                    axis=-1)
            return K.mean(xent_loss + kl_loss)

        def call(self, inputs):
            x = inputs[0]
            x_decoded_mean = inputs[1]
            loss = self.vae_loss(x, x_decoded_mean)
            self.add_loss(loss, inputs=inputs)
            return x

    y = CustomVariationalLayer()([x, x_decoded_mean])
    vae = Model(x, y)
    vae.compile(optimizer='rmsprop', loss=None)
    # build a model to project inputs on the latent space
    encoder = Model(x, z_mean)
    return vae, encoder


def build_autoencoder(input_dim, ngpu=1, layers_dim=[100, 10, 10],
                      activations=['tanh', 'tanh'],
                      inits=['glorot_uniform', 'glorot_normal'],
                      optimizer='adam',
                      drop=0.1, l2=1e-5,
                      loss='mse'):

    input_row = Input(shape=(input_dim,))

    for n, layer_dim in enumerate(layers_dim):
        if n == 0:
            encoded = Dense(layer_dim, activation=activations[0],
                            kernel_initializer=inits[0])(input_row)
            if drop > 0:
                encoded = Dropout(drop)(encoded)
        elif n < (len(layers_dim) - 1):
            encoded = Dense(layer_dim, activation=activations[0],
                            kernel_initializer=inits[0])(encoded)
            if drop > 0:
                encoded = Dropout(drop)(encoded)
        else:
            encoded = Dense(layer_dim, activation=activations[0],
                            activity_regularizer=regularizers.l2(l2),
                            kernel_initializer=inits[0])(encoded)

    encoder = Model(input_row, encoded)
    for n, layer_dim in enumerate(reversed(layers_dim[:-1])):
        if n == 0:
            decoded = Dense(layer_dim, activation=activations[0],
                            kernel_initializer=inits[0])(encoded)
            if drop > 0:
                decoded = Dropout(drop)(decoded)
        else:
            decoded = Dense(layer_dim, activation=activations[0],
                            kernel_regularizer=regularizers.l2(l2),
                            kernel_initializer=inits[0])(decoded)
            if drop > 0:
                decoded = Dropout(drop)(decoded)

    decoded = Dense(input_dim, activation=activations[1],
                    kernel_regularizer=regularizers.l2(l2),
                    kernel_initializer=inits[1])(decoded)

    autoencoder = Model(input_row, decoded)
    log.debug(autoencoder.summary())

    autoencoder.compile(optimizer=optimizer, loss=loss)
    return autoencoder, encoder


def standard(X):
    log.debug('Standarize')
    if X.dtype == 'bool':
        log.debug('Boolean data detected')
        loss = 'binary_crossentropy'
        Xs = X
    else:
        # Standarize
        ptp = X.ptp(axis=0)
        ptp[ptp == 0] = 1
        Xs = (X - X.min(axis=0)) / ptp
        loss = 'mse'
        log.debug('Done. AE Loss: {}'.format(loss))
    return Xs, loss


def run_ae(X, epochs=100, batch_size=128, verbose=0,  **kwargs):

    Xs, loss = standard(X)
    # AE
    ae_args = {'layers_dim': [100, 50,
                              min(max(X.shape[1] // 10, 5), 25)],
               'inits': ['glorot_normal', 'glorot_uniform'],
               'activations': ['tanh', 'sigmoid'], 'l2': 0,
               'optimizer': 'adagrad'}
    ae_args.update(kwargs)
    log.info('Training Autoencoder')
    ae, encoder = build_autoencoder(Xs.shape[1], **ae_args)
    ae.fit(Xs, Xs, batch_size=batch_size, epochs=epochs,
           shuffle=True, verbose=verbose,
           callbacks=[TensorBoard(log_dir='/tmp/autoencoder')])
    log.debug('Encoding')
    Xp = encoder.predict(Xs, verbose=False)
    log.debug('Computing reconstruction loss')
    X2 = ae.predict(Xs, verbose=False)
    error = ((X2 - Xs)**2).mean(axis=0)
    log.info('Done. Loss %s', ae.evaluate(Xs, Xs))
    return Xp, error, encoder


def run_vae(X, epochs=100, batch_size=128, verbose=0,  **kwargs):

    Xs, loss = standard(X)
    # VAE
    vae_args = {'layers_dim': [100, 5],
                'inits': ['glorot_normal', 'glorot_uniform'],
                'activations': ['tanh', 'sigmoid'], 'l2': 0,
                'optimizer': 'adagrad',
                'batch_size': batch_size}
    vae_args.update(kwargs)
    log.info('Training Variational Autoencoder')
    vae, encoder = build_vae(Xs.shape[1], **vae_args)
    vae.fit(Xs, Xs, batch_size=batch_size, epochs=epochs,
            shuffle=True, verbose=verbose,
            callbacks=[TensorBoard(log_dir='/tmp/autoencoder')])
    log.debug('Encoding')
    Xp = encoder.predict(Xs, verbose=False, batch_size=batch_size)
    log.debug('Computing reconstruction loss')
    X2 = vae.predict(Xs, verbose=verbose, batch_size=batch_size)
    error = ((X2 - Xs)**2).mean(axis=0)
    log.info('Done. Loss %s', vae.evaluate(Xs, Xs, batch_size=100))
    return Xp, error, encoder
