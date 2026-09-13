import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import argparse
import logging
from pathlib import Path
from omegaconf import OmegaConf

from src.models.bdh_loader import BDHLoader, create_bdh_model
from src.instrumentation.checkpoint_utils import CheckpointManager, create_checkpoint_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_synthetic_dataloader(config, batch_size: int = 32, num_batches: int = 1000):
    vocab_size = config.vocab_size
    max_seq_len = config.max_seq_len
    
    class SyntheticDataset(torch.utils.data.Dataset):
        def __init__(self, num_samples, seq_len, vocab_size):
            self.num_samples = num_samples
            self.seq_len = seq_len
            self.vocab_size = vocab_size
        
        def __len__(self):
            return self.num_samples
        
        def __getitem__(self, idx):
            input_ids = torch.randint(0, self.vocab_size, (self.seq_len,))
            labels = input_ids.clone()
            return {'input_ids': input_ids, 'labels': labels}
    
    dataset = SyntheticDataset(num_batches * batch_size, max_seq_len, vocab_size)
    return DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=4)


def train_model(model, dataloader, optimizer, criterion, device, epochs: int, 
                checkpoint_manager, model_type: str, config, training_config):
    model.train()
    
    for epoch in range(epochs):
        total_loss = 0.0
        num_batches = 0
        
        for batch_idx, batch in enumerate(dataloader):
            input_ids = batch['input_ids'].to(device)
            labels = batch['labels'].to(device)
            
            optimizer.zero_grad()
            
            outputs = model(input_ids)
            logits = outputs['logits']
            
            loss = criterion(logits.view(-1, logits.size(-1)), labels.view(-1))
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), training_config.gradient_clip)
            optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
            
            if batch_idx % 100 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, Batch {batch_idx}, Loss: {loss.item():.4f}")
        
        avg_loss = total_loss / max(num_batches, 1)
        logger.info(f"Epoch {epoch+1}/{epochs} completed. Average Loss: {avg_loss:.4f}")
        
        checkpoint_manager.save_model_checkpoint(
            model=model,
            optimizer=optimizer,
            scheduler=None,
            epoch=epoch + 1,
            step=(epoch + 1) * num_batches,
            loss=avg_loss,
            metrics={'train_loss': avg_loss},
            model_type=model_type,
            model_config=config,
            training_config=training_config,
            name=f"{model_type}_epoch{epoch+1}"
        )
    
    return model


def main():
    parser = argparse.ArgumentParser(description="Train small BDH model")
    parser.add_argument("--config", type=str, default="configs/default.yaml", help="Config file path")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--device", type=str, default="cuda", help="Device (cuda/cpu)")
    parser.add_argument("--output-dir", type=str, default="checkpoints/", help="Output directory")
    args = parser.parse_args()
    
    config = OmegaConf.load(args.config)
    
    config.training.batch_size = args.batch_size
    config.training.learning_rate = args.lr
    config.training.max_epochs = args.epochs
    config.training.device = args.device
    config.model.bdh.device = args.device
    config.paths.checkpoints_dir = args.output_dir
    
    device = torch.device(args.device)
    logger.info(f"Training on {device}")
    
    logger.info("Creating BDH model...")
    model = create_bdh_model(config.model.bdh)
    model = model.to(device)
    
    logger.info(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    logger.info("Creating dataloader...")
    dataloader = create_synthetic_dataloader(config.model.bdh, args.batch_size)
    
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=config.training.weight_decay
    )
    criterion = nn.CrossEntropyLoss()
    
    checkpoint_manager = create_checkpoint_manager(config)
    
    logger.info("Starting training...")
    model = train_model(
        model=model,
        dataloader=dataloader,
        optimizer=optimizer,
        criterion=criterion,
        device=device,
        epochs=args.epochs,
        checkpoint_manager=checkpoint_manager,
        model_type="bdh",
        config=config.model.bdh,
        training_config=config.training
    )
    
    final_path = Path(args.output_dir) / "models" / "bdh_final.pt"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        'model_state_dict': model.state_dict(),
        'config': OmegaConf.to_container(config.model.bdh, resolve=True),
    }, final_path)
    
    logger.info(f"Training complete! Final model saved to {final_path}")


if __name__ == "__main__":
    main()
