
import numpy as np
import tensorflow as tf
import time
from tensorflow.contrib import slim


def trainer(input_dim, num_samples, dataset, learning_rate=1e-3, batch_size=100, num_epoch=75, n_z=10):
  #input_dim = (28,28)
  model = VariantionalAutoencoder(input_dim, learning_rate=learning_rate,
                                  batch_size=batch_size, n_z=n_z)

  totalLoss = []
  testLoss = []
  validateLoss = []
  for epoch in range(num_epoch):
    start_time = time.time()
    epochLoss = []
    for iter in range(num_samples // batch_size):
      # Obtain a batch
      batch = dataset.train.next_batch(batch_size)
      #batch = batch[0].reshape([batch_size, 28, 28, 1])
      batch = batch[0]
      #print(batch.shape)
      # Execute the forward and the backward pass and report computed losses
      loss, recon_loss, latent_loss = model.run_single_step(batch)
      epochLoss.append(loss)
    totalLoss.append(sum(epochLoss) / len(epochLoss))
    delta_time = time.time() - start_time

    batch = dataset.validation.next_batch(10000)[0]
    x_hat = model.reconstructor(batch)
    vloss, _, _ = model.compute_loss(batch)
    validateLoss.append(vloss)

    batch = dataset.test.next_batch(10000)[0]
    x_hat = model.reconstructor(batch)
    tloss, _, _ = model.compute_loss(batch)
    testLoss.append(tloss)

    if epoch % 1 == 0:
      print('[Epoch {} Time {}s] Loss: {}, Recon loss: {}, Latent loss: {}'.format(epoch, delta_time, loss, recon_loss, latent_loss))
  print('training losses: ', totalLoss)
  print('validation losses: ', validateLoss)
  print('testing losses: ', testLoss)
  saver = tf.train.Saver()
  save_path = saver.save(model.sess, "tmp/model.ckpt")
  print('Model saved in path:', save_path)
  print('Done!')
  return model, totalLoss, validateLoss, testLoss


class VariantionalAutoencoder(object):

  def __init__(self, input_dim, learning_rate=1e-3, batch_size=100, n_z=10):
    self.learning_rate = learning_rate
    self.batch_size = batch_size
    self.n_z = n_z
    self.input_dim = input_dim

    self.build()

    #self.sess = tf.InteractiveSession(config=tf.ConfigProto(log_device_placement=True))
    self.sess = tf.InteractiveSession()
    self.sess.run(tf.global_variables_initializer())
    self.writer = tf.summary.FileWriter('graphs', self.sess.graph)

  # Build the netowrk and the loss functions
  def build(self):
    self.x = tf.placeholder(name='x', dtype=tf.float32, shape=[None, 784])

    # Encode
    # x -> z_mean, z_sigma -> z
    net = tf.reshape(self.x, [-1, 28, 28, 1], name='reshape1')
    net = slim.conv2d(net, 64, [3, 3], scope='conv1_1', activation_fn=tf.nn.elu)
    net = slim.max_pool2d(net, [2, 2], scope='pool1')
    net = slim.conv2d(net, 128, [3, 3], scope='conv3_2')
    net = slim.max_pool2d(net, [2, 2], scope='pool2')
    #net = slim.conv2d(net, 128, [3, 3], scope='conv3_3')
    #net = slim.max_pool2d(net, [2, 2], scope='pool3')
    net = slim.flatten(net)
    net = slim.fully_connected(net, 1024, scope='enc_fc1', activation_fn=tf.nn.elu)
    net = slim.dropout(net, 0.75, scope='dropout1')
    net = slim.fully_connected(net, 512, scope='enc_fc2', activation_fn=tf.nn.elu)
    net = slim.dropout(net, 0.75, scope='dropout2')
    f3 = slim.fully_connected(net, 256, scope='enc_fc3', activation_fn=tf.nn.elu)
    self.z_mu = slim.fully_connected(f3, self.n_z, scope='enc_fc4_mu', activation_fn=None)
    self.z_log_sigma_sq = slim.fully_connected(f3, self.n_z, scope='enc_fc4_sigma', activation_fn=None)
    eps = tf.random_normal(shape=tf.shape(self.z_log_sigma_sq),
                           mean=0, stddev=1, dtype=tf.float32)
    self.z = self.z_mu + tf.sqrt(tf.exp(self.z_log_sigma_sq)) * eps

    # Decode
    # shape is [1, 1, 2, 1]
    # z -> x_hat
    net = slim.fully_connected(self.z, 256, scope='dec_fc1', activation_fn=tf.nn.elu)
    # shape is [1, 1, 256, 1]
    net = slim.dropout(net, 0.75, scope='dropout3')
    # net = tf.reshape(g1, [-1, 16, 16, 1], name='reshape1')
    # net = slim.conv2d_transpose(net, 8, 3, activation_fn=tf.nn.elu)
    # net = slim.flatten(net)
    net = slim.fully_connected(net, 512, scope='dec_fc2', activation_fn=tf.nn.elu)
    net = slim.dropout(net, 0.75, scope='dropout4')
    net = slim.fully_connected(net, 1024, scope='dec_fc3', activation_fn=tf.nn.elu)
    net = slim.dropout(net, 0.75, scope='dropout5')
    self.x_hat = slim.fully_connected(net, 784, scope='dec_fc4', activation_fn=tf.sigmoid)

    # Loss
    # Reconstruction loss
    # Minimize the cross-entropy loss
    # H(x, x_hat) = -\Sigma x*log(x_hat) + (1-x)*log(1-x_hat)
    epsilon = 1e-10
    recon_loss = -tf.reduce_sum(
      self.x * tf.log( epsilon +self.x_hat) + ( 1 -self.x) * tf.log( epsilon + 1 -self.x_hat),
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

  def compute_loss(self, x):
    loss, recon_loss, latent_loss = self.sess.run(
      [self.total_loss, self.recon_loss, self.latent_loss],
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

  # x -> z_mu
  def transformer2(self, x):
    z_mu = self.sess.run(self.z_mu, feed_dict={self.x: x})
    return z_mu
