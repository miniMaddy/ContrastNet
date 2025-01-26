import tensorflow as tf
import numpy as np
import argparse
import socket
import importlib
import time
import os
import scipy.misc
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'models'))
sys.path.append(os.path.join(BASE_DIR, 'utils'))
import provider
import pc_util


parser = argparse.ArgumentParser()
parser.add_argument('--gpu', type=int, default=0, help='GPU to use [default: GPU 0]')
parser.add_argument('--model_contrast', default='contrastnet', help='Model name: contrastnet [default: contrastnet]')
parser.add_argument('--model_cluster', default='clusternet', help='Model name: clusternet [default: clusternet]')
parser.add_argument('--batch_size', type=int, default=64, help='Batch Size during training [default: 1]')
parser.add_argument('--num_point', type=int, default=512, help='Point Number [256/512/1024/2048] [default: 1024]')
parser.add_argument('--model_path', default='log/epoch_190.ckpt', help='model checkpoint file path [default: log/model.ckpt]')
parser.add_argument('--dump_dir', default='dump', help='dump folder path [dump]')
parser.add_argument('--visu', action='store_true', help='Whether to dump image for error case [default: False]')
FLAGS = parser.parse_args()


BATCH_SIZE = FLAGS.batch_size
NUM_POINT = FLAGS.num_point
MODEL_PATH = FLAGS.model_path
GPU_INDEX = FLAGS.gpu
MODEL_CONTRAST = importlib.import_module(FLAGS.model_contrast) # import network module
MODEL_CLUSTER = importlib.import_module(FLAGS.model_cluster) # import network module
DUMP_DIR = FLAGS.dump_dir
if not os.path.exists(DUMP_DIR): os.mkdir(DUMP_DIR)
LOG_FOUT = open(os.path.join(DUMP_DIR, 'log_evaluate.txt'), 'w')
LOG_FOUT.write(str(FLAGS)+'\n')

NUM_CLASSES = 2
HOSTNAME = socket.gethostname()

# ModelNet40 official train/test split
TRAIN_FILES = provider.getDataFiles(\
    os.path.join(BASE_DIR, 'data/shapenet_cut/train_files.txt'))
TEST_FILES = provider.getDataFiles(\
    os.path.join(BASE_DIR, 'data/shapenet_cut/test_files.txt'))

def log_string(out_str):
    LOG_FOUT.write(out_str+'\n')
    LOG_FOUT.flush()
    print(out_str)

def evaluate(num_votes):
    is_training = False

    with tf.device('/gpu:'+str(GPU_INDEX)):
        pointclouds_pl_1, labels_pl = MODEL_CONTRAST.placeholder_inputs(BATCH_SIZE, NUM_POINT)
        pointclouds_pl_2, labels_pl = MODEL_CONTRAST.placeholder_inputs(BATCH_SIZE, NUM_POINT)
        is_training_pl = tf.compat.v1.placeholder(tf.bool, shape=())
        # simple model
        pred, feature1, feature2, end_points = MODEL_CONTRAST.get_model(pointclouds_pl_1, pointclouds_pl_2, is_training_pl)
        loss = MODEL_CONTRAST.get_loss(pred, labels_pl, end_points)
        # Add ops to save and restore all the variables.
        saver = tf.compat.v1.train.Saver()

    # Create a session
    config = tf.compat.v1.ConfigProto()
    config.gpu_options.allow_growth = True
    config.allow_soft_placement = True
    config.log_device_placement = True
    sess = tf.compat.v1.Session(config=config)

    # Restore variables from disk.
    saver.restore(sess, MODEL_PATH)
    log_string("Model restored.")
    ops = {'pointclouds_pl_1': pointclouds_pl_1,
           'pointclouds_pl_2': pointclouds_pl_2,
           'labels_pl': labels_pl,
           'is_training_pl': is_training_pl,
           'pred': pred,
           'loss': loss,
           'feature': feature1}


    eval_one_epoch(sess, ops, num_votes)

def eval_one_epoch(sess, ops, num_votes=12, topk=1):
    is_training = False
    total_correct = 0
    total_seen = 0
    loss_sum = 0

    current_data_1 = np.empty([3*len(TEST_FILES), NUM_POINT, 3], dtype=float)
    current_data_2 = np.empty([3*len(TEST_FILES), NUM_POINT, 3], dtype=float)
    current_label  =  np.empty([3*len(TEST_FILES),1], dtype=int)

    fn = 0
    count = 0
    while fn < len(TEST_FILES) - 1:

        total_current = [];
        a1, a2, _ = provider.loadDataFile_cut_2(TEST_FILES[fn])

        idx = np.random.randint(a1.shape[0], size=NUM_POINT)
        a1 = a1[idx,:]
        idx = np.random.randint(a2.shape[0], size=NUM_POINT)
        a2 = a2[idx,:]
        total_current.append(a1)
        total_current.append(a2)

        fn = fn + 1;

        b1, b2, _ = provider.loadDataFile_cut_2(TEST_FILES[fn])

        idx = np.random.randint(b1.shape[0], size=NUM_POINT)
        b1 = b1[idx,:]
        idx = np.random.randint(b2.shape[0], size=NUM_POINT)
        b2 = b2[idx,:]
        total_current.append(b1)
        total_current.append(b2)

        fn = fn + 1;

        pair_num = 0
        for index in range(len(total_current)):
            for index2 in range(index + 1, len(total_current)):
                current_data_1[6*count+pair_num,:,:] = total_current[index]
                current_data_2[6*count+pair_num, :,:] = total_current[index2]
                if (index < 2) and (index2 >= 2):
                    current_label[6*count+pair_num,:] = 0
                else:
                    current_label[6*count+pair_num,:] = 1

                pair_num = pair_num + 1
        count = count + 1

    current_label = np.squeeze(current_label)


    file_size = current_data_1.shape[0]
    num_batches = file_size // BATCH_SIZE
    log_string('file_size: %d' % (file_size))
    log_string('num_batches: %d' % (num_batches))

    for batch_idx in range(num_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = (batch_idx+1) * BATCH_SIZE
        cur_batch_size = end_idx - start_idx
        log_string('batch: %d' % (batch_idx))
        # Aggregating BEG
        batch_loss_sum = 0 # sum of losses for the batch
        batch_pred_sum = np.zeros((cur_batch_size, NUM_CLASSES)) # score for classes
        # batch_pred_classes = np.zeros((cur_batch_size, NUM_CLASSES)) # 0/1 for classes
        for vote_idx in range(num_votes):
            rotated_data_1 = provider.rotate_point_cloud_by_angle(current_data_1[start_idx:end_idx, :, :],
                                              vote_idx/float(num_votes) * np.pi * 2)
            rotated_data_2 = provider.rotate_point_cloud_by_angle(current_data_2[start_idx:end_idx, :, :],
                                              vote_idx/float(num_votes) * np.pi * 2)
            feed_dict = {ops['pointclouds_pl_1']: rotated_data_1,
                         ops['pointclouds_pl_2']: rotated_data_2,
                         ops['labels_pl']: current_label[start_idx:end_idx],
                         ops['is_training_pl']: is_training}

            loss_val, pred_val, _ = sess.run([ops['loss'], ops['pred'], ops['feature']],
                                      feed_dict=feed_dict)
            batch_pred_sum += pred_val
            # batch_pred_val = np.argmax(pred_val, 1)
            # for el_idx in range(cur_batch_size):
            #     batch_pred_classes[el_idx, batch_pred_val[el_idx]] += 1
            batch_loss_sum += (loss_val * cur_batch_size / float(num_votes))
        # pred_val_topk = np.argsort(batch_pred_sum, axis=-1)[:,-1*np.array(range(topk))-1]
        # pred_val = np.argmax(batch_pred_classes, 1)
        pred_val = np.argmax(batch_pred_sum, 1)
        # Aggregating END

        correct = np.sum(pred_val == current_label[start_idx:end_idx])
        # correct = np.sum(pred_val_topk[:,0:topk] == label_val)
        total_correct += correct
        total_seen += cur_batch_size
        loss_sum += batch_loss_sum

    log_string('eval mean loss: %f' % (loss_sum / float(total_seen)))
    log_string('eval accuracy: %f' % (total_correct / float(total_seen)))


if __name__=='__main__':
    with tf.Graph().as_default():
        evaluate(num_votes=12)
    LOG_FOUT.close()
