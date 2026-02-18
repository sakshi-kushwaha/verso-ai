export const REELS = [
  {
    id: 1,
    title: 'The Birth of Neural Networks',
    category: 'DEEP LEARNING',
    pages: '1-4',
    body: 'Neural networks were inspired by the biological neural networks in the human brain. The perceptron, invented in 1958 by Frank Rosenblatt, was the first algorithmically described neural network. It consisted of a single layer of output nodes connected to inputs through weights. Despite initial excitement, the limitations of single-layer perceptrons led to a period known as the "AI winter." It wasn\'t until the development of backpropagation and multi-layer networks in the 1980s that the field was revitalized.',
    keywords: ['Perceptron', 'Backpropagation', 'AI Winter', 'Rosenblatt'],
    accent: '#6366F1',
  },
  {
    id: 2,
    title: 'Understanding Transformer Architecture',
    category: 'NLP',
    pages: '5-9',
    body: 'The Transformer architecture, introduced in the landmark paper "Attention Is All You Need" (2017), revolutionized natural language processing. Unlike recurrent neural networks (RNNs), Transformers process all tokens in parallel using a mechanism called self-attention. This allows them to capture long-range dependencies more effectively and train significantly faster on modern hardware.',
    keywords: ['Self-Attention', 'Parallelism', 'Embeddings', 'BERT'],
    accent: '#8B5CF6',
  },
  {
    id: 3,
    title: 'Gradient Descent Optimization',
    category: 'OPTIMIZATION',
    pages: '10-13',
    body: 'Gradient descent is the workhorse optimization algorithm of deep learning. The basic idea is simple: compute the gradient of the loss function with respect to the model parameters, then update the parameters in the direction that reduces the loss. Variants like SGD with momentum, Adam, and AdaGrad each offer different trade-offs between convergence speed and computational cost.',
    keywords: ['SGD', 'Adam', 'Learning Rate', 'Convergence'],
    accent: '#EC4899',
  },
  {
    id: 4,
    title: 'Convolutional Neural Networks',
    category: 'COMPUTER VISION',
    pages: '14-18',
    body: 'CNNs are specialized neural networks designed for processing grid-like data such as images. They use convolutional layers that apply learnable filters across the input, detecting features like edges, textures, and complex patterns at different scales. The key innovation is parameter sharing \u2014 the same filter is applied across the entire image, dramatically reducing the number of learnable parameters.',
    keywords: ['Convolution', 'Pooling', 'Feature Maps', 'ResNet'],
    accent: '#14B8A6',
  },
  {
    id: 5,
    title: 'Reinforcement Learning Basics',
    category: 'RL',
    pages: '19-22',
    body: 'Reinforcement learning (RL) is a paradigm where an agent learns to make decisions by interacting with an environment. The agent receives rewards or penalties based on its actions and learns a policy that maximizes cumulative reward over time. Key concepts include the exploration-exploitation trade-off, value functions, and policy gradients.',
    keywords: ['Agent', 'Reward', 'Policy', 'Q-Learning'],
    accent: '#F59E0B',
  },
];

export const FLASHCARDS = [
  { id: 1, reelId: 1, question: 'What was the first algorithmically described neural network?', answer: 'The Perceptron, invented by Frank Rosenblatt in 1958. It was a single-layer network that could learn to classify inputs into two categories.' },
  { id: 2, reelId: 2, question: 'What mechanism allows Transformers to process tokens in parallel?', answer: 'Self-attention. It computes relationships between all pairs of tokens simultaneously, replacing the sequential processing of RNNs.' },
  { id: 3, reelId: 3, question: 'What is the key difference between SGD and Adam optimizer?', answer: 'Adam combines momentum (tracking past gradients) with adaptive learning rates per parameter. SGD uses a fixed learning rate for all parameters.' },
  { id: 4, reelId: 4, question: 'Why do CNNs use parameter sharing?', answer: 'The same convolutional filter is applied across the entire input. This dramatically reduces parameters and enables the network to detect features regardless of their position in the image.' },
  { id: 5, reelId: 5, question: 'What is the exploration-exploitation trade-off in RL?', answer: 'The agent must balance exploring new actions (to discover potentially better strategies) versus exploiting known good actions (to maximize immediate reward).' },
];

