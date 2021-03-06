import tensorflow as tf
import numpy as np


def makeDenseClassifierModel(input_shape, layer_sizes):
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Flatten(input_shape=input_shape))

    for layer in layer_sizes[:-1]:
        print('layer:', layer)
        model.add(tf.keras.layers.Dense(layer, activation=tf.nn.relu))

    model.add(tf.keras.layers.Dense(layer_sizes[-1], activation=tf.nn.softmax))
    return model


def buildEncoder(input_shape, layer_sizes, latent_dim):
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Flatten(input_shape=input_shape))
    for layer in layer_sizes:
        model.add(tf.keras.layers.Dense(layer, activation='relu'))
    model.add(tf.keras.layers.Dense(latent_dim))
    model.summary()

    img = tf.keras.Input(shape=input_shape)
    encoded = model(img)

    return tf.keras.Model(img, encoded)


def buildConvEncoder(input_shape, layer_sizes, latent_dim):
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Reshape(input_shape, input_shape=input_shape))
    for layer in layer_sizes:
        model.add(tf.keras.layers.Conv2D(layer, (3, 3), activation='relu', padding='same'))
        model.add(tf.keras.layers.MaxPooling2D((2, 2), padding='same'))

    model.add(tf.keras.layers.Conv2D(latent_dim, (1, 1), padding='same'))
    model.add(tf.keras.layers.Flatten())
    model.summary()

    img = tf.keras.Input(shape=input_shape)
    encoded = model(img)

    return tf.keras.Model(img, encoded)


def buildDecoder(input_shape, layer_sizes, latent_dim):
    latent_shape = (latent_dim,)
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Flatten(input_shape=latent_shape))
    for layer in layer_sizes:
        model.add(tf.keras.layers.Dense(layer, activation='relu'))
    model.add(tf.keras.layers.Dense(np.product(input_shape), activation='sigmoid'))
    model.add(tf.keras.layers.Reshape(input_shape))
    model.summary()

    latent = tf.keras.Input(shape=latent_shape)
    decoded = model(latent)

    return tf.keras.Model(latent, decoded)


def Resize2DBilinear(size):
    return tf.keras.layers.Lambda(lambda image: tf.image.resize_bilinear(image, size, align_corners=True))


def buildConvDecoder(input_shape, layer_filters, layer_sizes, latent_dim):
    latent_shape = (latent_dim,)
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Reshape([1, 1, latent_dim], input_shape=latent_shape))
    for num_filters, image_size in zip(layer_filters, layer_sizes):
        model.add(tf.keras.layers.Conv2D(num_filters, (3, 3), activation='relu', padding='same'))
        model.add(Resize2DBilinear(image_size))

    model.add(tf.keras.layers.Conv2D(1, (3, 3), activation='sigmoid', padding='same'))
    model.summary()

    img = tf.keras.Input(shape=latent_shape)
    encoded = model(img)

    return tf.keras.Model(img, encoded)


def buildDiscriminator(layer_sizes, input_shape):
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.Flatten(input_shape=input_shape))
    for layer in layer_sizes:
        model.add(tf.keras.layers.Dense(layer, activation='relu'))
    model.add(tf.keras.layers.Dense(1, activation='sigmoid'))
    model.summary()

    latent = tf.keras.Input(shape=input_shape)
    validity = model(latent)

    return tf.keras.Model(latent, validity)

def makeVAE_GAN(input_shape, layer_sizes, latent_dim, optimizer, reconstructor_loss, discriminator_loss, use_conv):
    discriminator = buildDiscriminator(layer_sizes, input_shape)
    discriminator.compile(loss=discriminator_loss, optimizer=optimizer, metrics=['accuracy'])
    if use_conv:
        m = 2
        encoder = buildConvEncoder(input_shape, [4*m, 8*m, 16*m, 32*m, 64*m], latent_dim)
        decoder = buildConvDecoder(input_shape, [64*m, 32*m, 16*m, 8*m, 4*m], [(2, 2), (4, 4), (7, 7), (14, 14), (28, 28)], latent_dim)
    else:
        encoder = buildEncoder(input_shape, layer_sizes, latent_dim)
        decoder = buildDecoder(input_shape, layer_sizes, latent_dim)

    # the loss for the encoder and decoder is just a placeholder. We never actually use it
    encoder.compile(loss=reconstructor_loss, optimizer=optimizer)
    decoder.compile(loss=reconstructor_loss, optimizer=optimizer)

    x = tf.keras.Input(shape=input_shape)
    latent = encoder(x)
    x_hat = decoder(latent)

    reconstructor = tf.keras.Model(x, x_hat)
    reconstructor.summary()
    reconstructor.compile(loss=reconstructor_loss, optimizer=optimizer)

    discriminator.trainable = False
    valid = discriminator(x_hat)

    combined = tf.keras.Model(x, valid)
    combined.summary()
    combined.compile(loss=discriminator_loss, optimizer=optimizer)

    return encoder, decoder, discriminator, reconstructor, combined


def makeAdversarialAutoEncoder(input_shape, layer_sizes, latent_dim, optimizer, reconstructor_loss, discriminator_loss, use_conv):
    latent_shape = (latent_dim,)
    discriminator = buildDiscriminator(layer_sizes, latent_shape)
    discriminator.compile(loss=discriminator_loss, optimizer=optimizer, metrics=['accuracy'])

    # x
    # 28x28x1 
    # conv2d maxpool 14x14xF
    # conv2d maxpool 7x7xF
    # conv2d maxpool 4x4xF
    # conv2d maxpool 2x2xF
    # conv2d maxpool 1x1xF
    # conv2d 1x1xZ
    # z
    # conv2d resize 2x2xF
    # conv2d resize 4x4xF
    # conv2d resize 7x7xF
    # conv2d resize 14x14xF
    # conv2d resize 28x28xF
    # conv2d 28x28x1
    # x_hat

    if use_conv:
        m = 2
        encoder = buildConvEncoder(input_shape, [4*m, 8*m, 16*m, 32*m, 64*m], latent_dim)
        decoder = buildConvDecoder(input_shape, [64*m, 32*m, 16*m, 8*m, 4*m], [(2, 2), (4, 4), (7, 7), (14, 14), (28, 28)], latent_dim)
    else:
        encoder = buildEncoder(input_shape, layer_sizes, latent_dim)
        decoder = buildDecoder(input_shape, layer_sizes, latent_dim)

    # the loss for the encoder and decoder is just a placeholder. We never actually use it
    encoder.compile(loss=reconstructor_loss, optimizer=optimizer)
    decoder.compile(loss=reconstructor_loss, optimizer=optimizer)

    x = tf.keras.Input(shape=input_shape)
    latent = encoder(x)
    x_hat = decoder(latent)

    reconstructor = tf.keras.Model(x, x_hat)
    reconstructor.summary()
    reconstructor.compile(loss=reconstructor_loss, optimizer=optimizer)

    discriminator.trainable = False
    valid = discriminator(latent)

    combined = tf.keras.Model(x, valid)
    combined.summary()
    combined.compile(loss=discriminator_loss, optimizer=optimizer)

    return encoder, decoder, discriminator, reconstructor, combined