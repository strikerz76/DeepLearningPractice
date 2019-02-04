# from https://github.com/shaohua0116/VAE-Tensorflow

import numpy as np
import tensorflow as tf
from tensorflow.contrib.slim import fully_connected as fc
import matplotlib
import matplotlib.pyplot as plt
import time

#tf.enable_eager_execution()

current_time_m = lambda: int(round(time.time() * 1000))
current_time_s = lambda: time.time()

matplotlib.use('Agg')
plt.ioff()

from tensorflow.examples.tutorials.mnist import input_data

mnist = input_data.read_data_sets('MNIST_data', one_hot=True)
num_sample = mnist.train.num_examples
input_dim = mnist.train.images[0].shape[0]
w = h = 28

BATCH_SIZE = 100
TRAIN_BUF = 50000
VALIDATE_BUF = 10000
TEST_BUF = 10000

(train_images, _), (test_images, _) = tf.keras.datasets.mnist.load_data()
# Normalizing the images to the range of [0., 1.]

print( "train shape: ", train_images.shape )
print( "test shape: ", test_images.shape )
#train_images = train_images.reshape(train_images.shape[0], 28, 28, 1).astype('float32')
#test_images = test_images.reshape(test_images.shape[0], 28, 28, 1).astype('float32')
train_images = train_images.reshape(train_images.shape[0], 784).astype('float32')
test_images = test_images.reshape(test_images.shape[0], 784).astype('float32')
print( "train shape: ", train_images.shape )
print( "test shape: ", test_images.shape )
train_images /= 255.
test_images /= 255.

train_images = tf.random_shuffle(train_images, seed=1234)
print( "shuffled train shape: ", train_images.shape )
train_images, validate_images = tf.split(train_images, [TRAIN_BUF, VALIDATE_BUF], 0)

print( "train shape: ", train_images.shape )
print( "validate shape: ", validate_images.shape )
print( "test shape: ", test_images.shape )


def generator():
    for i in range(int(train_images.shape[0].value/BATCH_SIZE)):
        yield train_images[i*BATCH_SIZE: (i+1)*BATCH_SIZE]


# ds = tf.data.Dataset.from_tensor_slices(train_images).batch(100)
# print(ds.output_types)
# print(ds.output_shapes)
# for element in ds:
#   print(element)

#for element in batch_gen:
#    print(element);


# Binarization
#train_images[train_images >= .5] = 1.
#train_images[train_images < .5] = 0.
#test_images[test_images >= .5] = 1.
#test_images[test_images < .5] = 0.



class VariantionalAutoencoder(object):

    def __init__(self, learning_rate=1e-3, batch_size=100, n_z=10):
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.n_z = n_z

        self.build()

        self.sess = tf.InteractiveSession()
        self.sess.run(tf.global_variables_initializer())

    # Build the netowrk and the loss functions
    def build(self):
        self.x = tf.placeholder(name='x', dtype=tf.float32, shape=[None, input_dim])

        # Encode
        # x -> z_mean, z_sigma -> z                                                         # input 28*28= 784
        f1 = fc(self.x, 512, scope='enc_fc1', activation_fn=tf.nn.elu)                      # fully connected 512
        f2 = fc(f1, 384, scope='enc_fc2', activation_fn=tf.nn.elu)                          # fully connected 384
        f3 = fc(f2, 256, scope='enc_fc3', activation_fn=tf.nn.elu)                          # fully connected 256
        self.z_mu = fc(f3, self.n_z, scope='enc_fc4_mu', activation_fn=None)                # fully connected to mu (default 10)
        self.z_log_sigma_sq = fc(f3, self.n_z, scope='enc_fc4_sigma', activation_fn=None)   # fully connected to sigma (default 10)
        eps = tf.random_normal(shape=tf.shape(self.z_log_sigma_sq),                         # reparam trick
                               mean=0, stddev=1, dtype=tf.float32)
        self.z = self.z_mu + tf.sqrt(tf.exp(self.z_log_sigma_sq)) * eps                     # combine mu with sigma * normal

        # Decode
        # z -> x_hat
        g1 = fc(self.z, 256, scope='dec_fc1', activation_fn=tf.nn.elu)                      # fully connected from 2*n_z to 256
        g2 = fc(g1, 384, scope='dec_fc2', activation_fn=tf.nn.elu)                          # fully connected to 384
        g3 = fc(g2, 512, scope='dec_fc3', activation_fn=tf.nn.elu)                          # fully connected to 512
        self.x_hat = fc(g3, input_dim, scope='dec_fc4', activation_fn=tf.sigmoid)           # fully connected to 784

        # Loss
        # Reconstruction loss
        # Minimize the cross-entropy loss
        # H(x, x_hat) = -\Sigma x*log(x_hat) + (1-x)*log(1-x_hat)
        epsilon = 1e-10
        recon_loss = -tf.reduce_sum(
            self.x * tf.log(epsilon+self.x_hat) + (1-self.x) * tf.log(epsilon+1-self.x_hat),
            axis=1
        )
        self.recon_loss = tf.reduce_mean(recon_loss)

        # Latent loss
        # Kullback Leibler divergence: measure the difference between two distributions
        # Here we measure the divergence between the latent distribution and N(0, 1)
        latent_loss = -0.5 * tf.reduce_sum(
            1 + self.z_log_sigma_sq - tf.square(self.z_mu) - tf.exp(self.z_log_sigma_sq), axis=1)
        self.latent_loss = tf.reduce_mean(latent_loss)

        self.total_loss = tf.reduce_mean(recon_loss + latent_loss)
        self.train_op = tf.train.AdamOptimizer(
            learning_rate=self.learning_rate).minimize(self.total_loss)
        return

    # Execute the forward and the backward pass
    def run_single_step(self, x):
        _, loss, recon_loss, latent_loss = self.sess.run(
            [self.train_op, self.total_loss, self.recon_loss, self.latent_loss],
            feed_dict={self.x: x}
        )
        return loss, recon_loss, latent_loss

    # x -> x_hat
    def reconstructor(self, x):
        x_hat = self.sess.run(self.x_hat, feed_dict={self.x: x})
        return x_hat

    # z -> x
    def generator(self, z):
        x_hat = self.sess.run(self.x_hat, feed_dict={self.z: z})
        return x_hat

    # x -> z
    def transformer(self, x):
        z = self.sess.run(self.z, feed_dict={self.x: x})
        return z

    def closeSession(self):
        self.sess.close()

def trainer(train_images, learning_rate=1e-3, batch_size=100, num_epoch=75, n_z=10):
    model = VariantionalAutoencoder(learning_rate=learning_rate,
                                    batch_size=batch_size, n_z=n_z)

    for epoch in range(num_epoch):
        startTime = current_time_m()
        train_images = tf.random_shuffle(train_images, seed=1234)
        batch_gen = generator()
        for batch2 in batch_gen:
            print(batch2)
            loss, recon_loss, latent_loss = model.run_single_step(batch2.eval())

        # for iter in range(num_sample // batch_size):
        #     # Obtain a batch
        #     batch = mnist.train.next_batch(batch_size)
        #     # Execute the forward and the backward pass and report computed losses
        #     loss, recon_loss, latent_loss = model.run_single_step(batch[0])
        deltaTime_s = (current_time_m() - startTime)/1000
        if epoch % 1 == 0:
            print('[Epoch {} Time {}] Loss: {}, Recon loss: {}, Latent loss: {}'.format(
                epoch, deltaTime_s, loss, recon_loss, latent_loss))

    print('Done!')
    return model

# Train the model
model = trainer(train_images, learning_rate=1e-4,  batch_size=100, num_epoch=5, n_z=5)

# Test the trained model: reconstruction
batch = mnist.test.next_batch(100)
x_reconstructed = model.reconstructor(batch[0])

n = np.sqrt(model.batch_size).astype(np.int32)
I_reconstructed = np.empty((h*n, 2*w*n))
for i in range(n):
    for j in range(n):
        x = np.concatenate(
            (x_reconstructed[i*n+j, :].reshape(h, w),
             batch[0][i*n+j, :].reshape(h, w)),
            axis=1
        )
        I_reconstructed[i*h:(i+1)*h, j*2*w:(j+1)*2*w] = x

fig = plt.figure()
plt.imshow(I_reconstructed, cmap='gray')
plt.savefig('I_reconstructed.png')
plt.close(fig)

# Test the trained model: generation
# Sample noise vectors from N(0, 1)
z = np.random.normal(size=[model.batch_size, model.n_z])
x_generated = model.generator(z)

n = np.sqrt(model.batch_size).astype(np.int32)
I_generated = np.empty((h*n, w*n))
for i in range(n):
    for j in range(n):
        I_generated[i*h:(i+1)*h, j*w:(j+1)*w] = x_generated[i*n+j, :].reshape(28, 28)

fig = plt.figure()
plt.imshow(I_generated, cmap='gray')
plt.savefig('I_generated.png')
plt.close(fig)

tf.reset_default_graph()
model.closeSession()
# Train the model with 2d latent space
model_2d = trainer(train_images, learning_rate=1e-4,  batch_size=100, num_epoch=5, n_z=2)

# Test the trained model: transformation
batch = mnist.test.next_batch(3000)
z = model_2d.transformer(batch[0])
fig = plt.figure()
plt.scatter(z[:, 0], z[:, 1], c=np.argmax(batch[1], 1))
plt.colorbar()
plt.grid()
plt.savefig('I_transformed.png')
plt.close(fig)

# Test the trained model: transformation
n = 100
x = np.linspace(-2, 2, n)
y = np.linspace(-2, 2, n)

I_latent = np.empty((h*n, w*n))
for i, yi in enumerate(x):
    for j, xi in enumerate(y):
        z = np.array([[xi, yi]]*model_2d.batch_size)
        x_hat = model_2d.generator(z)
        I_latent[(n-i-1)*28:(n-i)*28, j*28:(j+1)*28] = x_hat[0].reshape(28, 28)

fig = plt.figure(num=None, figsize=(n*28/100.0, n*28/100.0), dpi=100)
plt.imshow(I_latent, cmap="gray")
plt.savefig('I_latent.png')
plt.close(fig)

model_2d.closeSession()